# scrapers/kokusai_center.py Ver.2.0 + DB投入機能
import os
import json
import time
import hashlib
import unicodedata
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from event_notify.utils.parser import split_and_normalize, JST

# Supabase投入用（オプション）
try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    load_dotenv()
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# ---- メタ情報（変更に強いヘッダ部） -----------------------------------------
META = {
    "name": "kokusai_center",
    "venue": "福岡国際センター",
    "venue_code": "c",
    "url": "https://www.marinemesse.or.jp/kokusai/event/",
    "schema_version": "1.0",
    "selector_profile": "primary: table.table_list01>tr / fallback: table>tr (2+ tds)",
}

BASE_URL = META["url"]
SELECTORS = {
    "primary_rows": "table.table_list01 tr",
    "fallback_rows": "table tr",
}

# ---- HTTP / Fetch ------------------------------------------------------------
DEFAULT_UA = (
    os.getenv("SCRAPER_UA")
    or "event_notify-bot/1.0 (+contact: your-mail-or-site) "
       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.marinemesse.or.jp/",
    "Connection": "keep-alive",
}
DEBUG = os.getenv("DEBUG_IC", "0") == "1"

def _storage_path(date_str: str, code: str) -> Path:
    """共通のストレージパス生成"""
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"

def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _normalize_for_hash(s: str) -> str:
    """ハッシュ用の軽量正規化"""
    if s is None:
        return ""
    x = unicodedata.normalize("NFKC", s)
    x = x.replace(""", '"').replace(""", '"').replace("‟", '"').replace("〝", '"').replace("〞", '"')
    x = x.replace("'", "'").replace("'", "'").replace("＇", "'")
    x = re.sub(r"\s+", " ", x).strip()
    return x

def get_target_date_range() -> tuple[str, str]:
    """当月1日～翌月末日の期間を取得（Ver.2.0用）"""
    today = datetime.now(JST)
    
    # 当月1日
    start_date = today.replace(day=1)
    
    # 翌月末日
    next_month_first = start_date + relativedelta(months=1)
    end_date = next_month_first + relativedelta(months=1) - timedelta(days=1)
    
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

def filter_date_range(items: List[Dict], start_date: str, end_date: str) -> List[Dict]:
    """指定期間内のイベントのみ抽出"""
    return [e for e in items if start_date <= e.get("date", "") <= end_date]

def _resolve_target_date() -> str:
    """JST基準のターゲット日（上書き可）"""
    override = os.getenv("SCRAPER_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")

# ---- SUPABASE FUNCTIONS -----------------------------------------------------
def get_supabase_client() -> Client:
    """Supabaseクライアントを取得"""
    if not SUPABASE_AVAILABLE:
        raise RuntimeError("Supabase依存関係が不足: pip install supabase python-dotenv")
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        raise RuntimeError("環境変数 SUPABASE_URL, SUPABASE_KEY が設定されていません")
    
    return create_client(url, key)

def save_to_supabase(events: List[Dict]) -> None:
    """イベントデータをSupabaseに保存"""
    if not events:
        print(f"[{META['name']}] DB投入: データなし")
        return
    
    try:
        supabase = get_supabase_client()
        
        # JSONからSupabase形式に変換
        db_records = []
        for event in events:
            record = {
                "date": event.get("date"),
                "time": event.get("time"),  # NULLも許可
                "title": event.get("title", ""),
                "venue": event.get("venue", ""),
                "source_url": event.get("source", ""),
                "data_hash": event.get("hash", ""),
                "event_type": "auto",
                "notes": event.get("notes")  # NULLも許可
            }
            db_records.append(record)
        
        # バッチ挿入（重複は無視）
        result = supabase.table('events').upsert(
            db_records,
            on_conflict="data_hash"  # 重複時は無視
        ).execute()
        
        print(f"[{META['name']}] DB投入成功: {len(result.data)}件")
        
    except Exception as e:
        print(f"[{META['name']}][ERROR] DB投入失敗: {e}")
        # JSON保存は継続（DB失敗は致命的ではない）

def _requests_session() -> requests.Session:
    retry = Retry(
        total=3, connect=2, read=2,
        backoff_factor=0.7,
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s = requests.Session()
    s.headers.update(HEADERS)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

def _fetch_html(url: str) -> str:
    """段階的フェッチ: requests → cloudscraper（必要時のみ）"""
    sess = _requests_session()
    r = sess.get(url, timeout=20)
    if DEBUG:
        print(f"[{META['name']}] fetch status={r.status_code} len={len(r.text or '')}")
    if r.status_code == 200 and r.text:
        return r.text

    # フォールバック（必要時のみ）
    time.sleep(1.0)
    try:
        import cloudscraper  # type: ignore
    except ImportError as e:
        raise RuntimeError("cloudscraper 未インストール。`pip install cloudscraper`") from e

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False, "desktop": True},
        delay=5,
    )
    scraper.headers.update(HEADERS)
    r2 = scraper.get(url, timeout=25)
    if DEBUG:
        print(f"[{META['name']}] cloudscraper status={r2.status_code} len={len(r2.text or '')}")
    if r2.status_code != 200 or not r2.text:
        raise RuntimeError(f"cloudscraperでも取得失敗: status={r2.status_code}")
    return r2.text

def _extract_rows(soup: BeautifulSoup) -> List:
    rows = soup.select(SELECTORS["primary_rows"])
    if not rows or len(rows) <= 1:
        rows = soup.select(SELECTORS["fallback_rows"])
    return rows

def fetch_month_events(url: str, year: int, month: int) -> List[Dict[str, str]]:
    """指定月のイベントを取得"""
    try:
        html = _fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        events = []
        rows = _extract_rows(soup)

        for tr in rows:
            # ヘッダ行スキップ
            if tr.find("th"):
                continue
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            # 1列目（日付・時間）改行をスペースに
            dt_text = " ".join(tds[0].get_text(" ", strip=True).split())

            # 2列目（タイトル）リンク優先
            a = tds[1].find("a")
            title = a.get_text(" ", strip=True) if a else tds[1].get_text(" ", strip=True)

            # ナビ行/空行除外
            if not title or "前月" in title or "翌月" in title:
                continue

            events.append({
                "datetime": dt_text, 
                "title": title,
                "source_month": f"{year}-{month:02d}"
            })

        return events

    except Exception as e:
        print(f"[{META['name']}] Failed to fetch {year}-{month:02d}: {e}")
        return []

def fetch_multi_month_events() -> List[Dict[str, str]]:
    """当月1日～翌月末日の2ヶ月分を取得"""
    all_events = []
    current_month = datetime.now(JST).replace(day=1)
    
    # 当月+翌月の2ヶ月分
    for i in range(2):
        target = current_month + relativedelta(months=i)
        url = f"{BASE_URL}?yy={target.year}&mm={target.month}"
        
        print(f"[{META['name']}] Fetching {target.year}-{target.month:02d} from {url}")
        month_events = fetch_month_events(url, target.year, target.month)
        all_events.extend(month_events)
    
    return all_events

def main():
    t0 = time.time()
    target_date = _resolve_target_date()

    # Ver.2.0: 常に2ヶ月分取得
    raw = fetch_multi_month_events()
    
    # 期間範囲計算（当月1日～翌月末日）
    start_date, end_date = get_target_date_range()
    print(f"[{META['name']}] Target range: {start_date} ~ {end_date}")

    # 共通正規化＆展開
    normalized = []
    for e in raw:
        normalized.extend(split_and_normalize(e["datetime"], e["title"], META["venue"]))

    # 期間フィルタリング（当月1日～翌月末日）
    all_events = filter_date_range(normalized, start_date, end_date)

    # 重複排除＆メタ付与（全期間データ - Ver.2.0用）
    seen = set()
    out = []
    extracted_at = datetime.now(JST).isoformat()

    for it in all_events:
        title_norm = _normalize_for_hash(it.get("title", ""))
        venue_norm = _normalize_for_hash(it.get("venue", ""))
        date_part = it.get("date", "")
        time_part = it.get("time") or ""

        key = f"{date_part}|{time_part}|{title_norm}|{venue_norm}"
        h = _sha1(key)
        if h in seen:
            continue
        seen.add(h)

        out.append({
            "schema_version": META["schema_version"],
            **it,
            "source": BASE_URL,
            "hash": h,
            "extracted_at": extracted_at,
        })

    # 整列（date, time, title）
    def sort_key(ev):
        t = ev.get("time")
        tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
        return (ev.get("date", ""), tkey, ev.get("title", ""))
    
    out.sort(key=sort_key)

    # JSON保存（storage/{target_date}_c.json）— Ver.2.0: 全期間データを保存
    path = _storage_path(target_date, META['venue_code'])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Supabase投入（Ver.2.0用・新機能）
    db_enabled = os.getenv("ENABLE_DB_SAVE", "0") == "1"
    if db_enabled and SUPABASE_AVAILABLE:
        save_to_supabase(out)
    elif db_enabled:
        print(f"[{META['name']}] DB投入スキップ: Supabase依存関係不足")

    ms = int((time.time() - t0) * 1000)
    print(f"[{META['name']}] date={target_date} items={len(out)} range={start_date}~{end_date} ms={ms} → {path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 失敗時：ファイルは生成しない（ディスパッチ側がmissing検出）
        msg = str(e).replace("\n", " ")
        print(f"[{META['name']}][ERROR] msg=\"{msg}\"")
        # exit 0（全体は止めない）
