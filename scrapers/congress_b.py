# scrapers/congress_b.py Ver.2.0 + DB投入機能
# 福岡国際会議場（思い出ネーム: コングレスB）
# 出力：storage/{date}_d.json（schema_version=1.0）
# Ver.2.0: 当月1日～翌月末日の2ヶ月分データを保存 + Supabase投入

from __future__ import annotations
import os
import re
import json
import time
import hashlib
import unicodedata
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup

# parser.py をインポート
try:
    from utils.parser import split_and_normalize
except ImportError:
    # モジュールパス問題の場合のフォールバック
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from utils.parser import split_and_normalize

# Supabase投入用（オプション）
try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    load_dotenv()
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# ========= META =========
META = {
    "name": "congress_b",
    "venue": "福岡国際会議場",
    "code": "d",
    "url_candidates": [
        "https://www.marinemesse.or.jp/congress/event/",
        #"https://www.marinemesse.or.jp/congress/schedule/",
        #"https://www.marinemesse.or.jp/congress/",
    ],
    "schema_version": "1.0",
    "selector_profile": "primary: table that has headers 各列『日時/イベント名/主催者』 / alt: any table with similar header",
    "pagination": {
        "next_selector": "a[rel='next'], .pagination a",
        "max_pages": 5,
    },
}

BASE_URL = META["url_candidates"][0]

# ========= SELECTORS =========
SELECTORS = {
    "primary_table_match": ("日時", "イベント名", "主催者"),
    "alt_table_any": True,
}

# ========= 環境・共通 =========
JST = timezone(timedelta(hours=9))

def _split_and_normalize(s: str) -> str:
    if not s:
        return ""
    s = (
        s.replace(""", '"').replace(""", '"')
         .replace("'", "'").replace("'", "'")
         .replace("〜", "～").replace("―", "－")
    )
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _normalize_for_hash(s: str) -> str:
    """ハッシュ用の軽量正規化"""
    if s is None:
        return ""
    x = unicodedata.normalize("NFKC", s)
    x = x.replace(""", '"').replace(""", '"').replace("‟", '"').replace("〝", '"').replace("〞", '"')
    x = x.replace("'", "'").replace("'", "'").replace("＇", "'")
    x = re.sub(r"\s+", " ", x).strip()
    return x

def _sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _storage_path(date_str: str, code: str) -> Path:
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"

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
    """SCRAPER_TARGET_DATE=YYYY-MM-DD があればそれを優先。なければJSTの今日。"""
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

def _make_requests_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "event_notify (congress_b) / maintainer: your-contact",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.marinemesse.or.jp/",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    })
    retries = Retry(
        total=3,
        backoff_factor=0.7,
        status_forcelist=(403, 429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def _fetch_html(url: str, sess: requests.Session, timeout: float = 20.0) -> Optional[str]:
    try:
        r = sess.get(url, timeout=timeout)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", "") and r.text:
            return r.text
    except Exception:
        pass
    # fallback（任意）
    try:
        time.sleep(1.2)
        import cloudscraper  # type: ignore
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False, "desktop": True},
            delay=5
        )
        scraper.headers.update(sess.headers)
        r2 = scraper.get(url, timeout=timeout + 5)
        if r2.status_code == 200 and "text/html" in r2.headers.get("Content-Type", "") and r2.text:
            return r2.text
    except Exception:
        pass
    return None

# ========= パース =========
def _find_event_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    for t in soup.find_all("table"):
        header_text = _split_and_normalize(t.get_text(" ", strip=True))
        if all(key in header_text for key in SELECTORS["primary_table_match"]):
            return t
    tables = soup.find_all("table")
    return tables[0] if tables else None

def _parse_table(table: BeautifulSoup) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    rows = table.find_all("tr")
    if not rows:
        return events
    for tr in rows[1:]:
        tds = tr.find_all(["td", "th"])
        if len(tds) < 2:
            continue
        when_raw = _split_and_normalize(tds[0].get_text(" ", strip=True))
        title_cell = tds[1]
        a = title_cell.find("a")
        title_raw = _split_and_normalize(a.get_text(" ", strip=True) if a else title_cell.get_text(" ", strip=True))
        link = a.get("href") if a and a.has_attr("href") else None
        if not when_raw or not title_raw:
            continue
        if link and link.startswith("/"):
            link = "https://www.marinemesse.or.jp" + link
        events.append({"when": when_raw, "title": title_raw, "link": link or BASE_URL})
    return events

def _materialize_events(rows: List[Dict[str, str]]) -> List[Dict]:
    base_year = datetime.now(JST).year
    out: List[Dict] = []
    
    for r in rows:
        when = r["when"]
        title = r["title"]
        source = r["link"]
        
        # parser.py の split_and_normalize を使用
        parsed_events = split_and_normalize(when, title, META["venue"], base_year)
        
        for ev in parsed_events:
            item = {
                "schema_version": META["schema_version"],
                "date": ev["date"],
                "title": ev["title"],
                "venue": ev["venue"],
                "source": source,
            }
            
            # 時刻があれば追加
            if ev.get("time"):
                item["time"] = ev["time"]
            else:
                # 時刻未定の場合、元の文字列をnotesに保存
                item["notes"] = when
                
            out.append(item)
    
    return out

def scrape_month_events(url: str, year: int, month: int, sess: requests.Session) -> List[Dict]:
    """指定月のイベントを取得"""
    try:
        html = _fetch_html(url, sess)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        table = _find_event_table(soup)
        if not table:
            return []
        rows = _parse_table(table)
        items = _materialize_events(rows)
        
        # source_month 情報を追加
        for item in items:
            item["source_month"] = f"{year}-{month:02d}"
        
        return items

    except Exception as e:
        print(f"[{META['name']}] Failed to fetch {year}-{month:02d}: {e}")
        return []

def fetch_multi_month_events(sess: requests.Session) -> List[Dict]:
    """当月1日～翌月末日の2ヶ月分を取得"""
    all_events = []
    current_month = datetime.now(JST).replace(day=1)
    
    # 当月+翌月の2ヶ月分
    for i in range(2):
        target = current_month + relativedelta(months=i)
        url = f"{BASE_URL}?yy={target.year}&mm={target.month}"
        
        print(f"[{META['name']}] Fetching {target.year}-{target.month:02d} from {url}")
        month_events = scrape_month_events(url, target.year, target.month, sess)
        all_events.extend(month_events)
    
    return all_events

def _dedupe_and_hash(items: List[Dict]) -> List[Dict]:
    seen = set()
    norm_items: List[Dict] = []
    extracted_at = datetime.now(JST).isoformat()
    
    for ev in items:
        title_norm = _normalize_for_hash(ev.get("title", ""))
        venue_norm = _normalize_for_hash(ev.get("venue", ""))
        date_part = ev.get("date", "")
        time_part = ev.get("time") or ""

        key = f"{date_part}|{time_part}|{title_norm}|{venue_norm}"
        h = _sha1_hex(key)
        if h in seen:
            continue
        seen.add(h)
        
        ev["hash"] = h
        ev["extracted_at"] = extracted_at
        norm_items.append(ev)
    
    def sort_key(e: Dict) -> Tuple:
        t = e.get("time")
        tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
        return (e.get("date", ""), tkey, _normalize_for_hash(e.get("title", "")))
    
    return sorted(norm_items, key=sort_key)

# ========= メイン =========
def main():
    t0 = time.time()
    sess = _make_requests_session()
    target_date = _resolve_target_date()

    # Ver.2.0: 常に2ヶ月分取得
    collected = fetch_multi_month_events(sess)
    
    # 期間範囲計算（当月1日～翌月末日）
    start_date, end_date = get_target_date_range()
    print(f"[{META['name']}] Target range: {start_date} ~ {end_date}")

    # 期間フィルタリング（当月1日～翌月末日）
    all_events = filter_date_range(collected, start_date, end_date)

    # 重複排除＆ハッシュ付与（全期間データ - Ver.2.0用）
    items_to_save = _dedupe_and_hash(all_events)

    # 保存（storage/{target_date}_d.json）— Ver.2.0: 全期間データを保存
    outpath = _storage_path(target_date, META["code"])
    with outpath.open("w", encoding="utf-8") as f:
        json.dump(items_to_save, f, ensure_ascii=False, indent=2)

    # Supabase投入（Ver.2.0用・新機能）
    db_enabled = os.getenv("ENABLE_DB_SAVE", "0") == "1"
    if db_enabled and SUPABASE_AVAILABLE:
        save_to_supabase(items_to_save)
    elif db_enabled:
        print(f"[{META['name']}] DB投入スキップ: Supabase依存関係不足")

    # ログ
    elapsed_ms = int((time.time() - t0) * 1000)
    print(f"[{META['name']}] date={target_date} items={len(items_to_save)} range={start_date}~{end_date} ms={elapsed_ms} → {outpath}")

if __name__ == "__main__":
    main()
