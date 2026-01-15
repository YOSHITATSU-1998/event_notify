# scrapers/marinemesse_a.py Ver.2.0 + DB投入機能
import os
import json
import time
import re
import unicodedata
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from utils.parser import split_and_normalize, JST

# Supabase投入用（オプション）
try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    load_dotenv()
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# ---- META / SELECTORS -------------------------------------------------------
META = {
    "name": "marinemesse_a",
    "venue": "マリンメッセA館",
    "url": "https://www.marinemesse.or.jp/messe/event/",
    "schema_version": "1.0",
    "selector_profile": "table > tr with 2+ tds; alt: .event-list .event",
}
BASE_URL = META["url"]
VENUE = META["venue"]
SCHEMA_VERSION = META["schema_version"]

SELECTORS = {
    # 1st: 安定（現行のテーブル行想定）
    "primary": "table tr",
    # 2nd: フォールバック（将来 .event-list などに変わった場合）
    "fallback": ".event-list .event, .events .event, .eventItem",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EventBot/1.0; +https://example.com/contact)"
}

# ---- UTILS ------------------------------------------------------------------
def _storage_path(date_str: str, code: str) -> Path:
    """congress_b.py と同じ方式で storage パス生成"""
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"

def sha1(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _normalize_for_hash(s: str) -> str:
    """
    ハッシュ用の軽量正規化：
      - NFKCで全角/半角を統一
      - 引用符ゆれを統一（" " ‟ 〝 〞 → "、 ' ' ＇ → '）
      - 連続空白を1つに圧縮
      - 前後空白削除
    """
    if s is None:
        return ""
    x = unicodedata.normalize("NFKC", s)
    x = x.replace(""", '"').replace(""", '"').replace("‟", '"').replace("〝", '"').replace("〞", '"')
    x = x.replace("'", "'").replace("'", "'").replace("＇", "'")
    x = re.sub(r"\s+", " ", x).strip()
    return x

def resolve_target_date() -> str:
    """環境変数でターゲット日付を上書き可能（YYYY-MM-DD）。未指定ならJST今日"""
    override = os.getenv("SCRAPER_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")

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

# ---- SCRAPING ---------------------------------------------------------------
def fetch_month_events(url: str, year: int, month: int) -> List[Dict]:
    """指定月のイベントを取得"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        events = []

        # Primary: table rows
        rows = soup.select(SELECTORS["primary"])
        if rows:
            for tr in rows:
                tds = [td.get_text(" ", strip=True) for td in tr.select("td")]
                if len(tds) >= 2:
                    events.append({
                        "datetime": tds[0], 
                        "title": tds[1],
                        "source_month": f"{year}-{month:02d}"
                    })

        # Fallback: common event-card patterns
        if not events:
            for ev in soup.select(SELECTORS["fallback"]):
                text = ev.get_text(" ", strip=True)
                parts = re.split(r"\s{2,}| {1,}—| {1,}–| {1,}-", text)
                if len(parts) >= 2:
                    events.append({
                        "datetime": parts[0], 
                        "title": parts[-1],
                        "source_month": f"{year}-{month:02d}"
                    })

        return events

    except Exception as e:
        print(f"[{META['name']}] Failed to fetch {year}-{month:02d}: {e}")
        return []

def fetch_multi_month_events() -> List[Dict]:
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

# ---- MAIN -------------------------------------------------------------------
def main():
    t0 = time.time()

    target_date = resolve_target_date()
    
    # 1) 全期間スクレイピング（2ヶ月分）
    raw = fetch_multi_month_events()
    
    # 期間範囲計算（当月1日～翌月末日）
    start_date, end_date = get_target_date_range()
    print(f"[{META['name']}] Target range: {start_date} ~ {end_date}")

    # 2) 正規化（「8.29(金) 10:30～ …」→ date/time/title/venue の配列に展開）
    normalized: List[Dict] = []
    for e in raw:
        normalized.extend(split_and_normalize(e["datetime"], e["title"], VENUE))

    # 3) 期間フィルタリング（当月1日～翌月末日）
    all_events = filter_date_range(normalized, start_date, end_date)

    # 4) 重複排除＆メタ付与（全期間データ - Ver.2.0用）
    seen = set()
    out: List[Dict] = []
    extracted_at = datetime.now(JST).isoformat()

    for it in all_events:
        title_norm = _normalize_for_hash(it.get("title", ""))
        venue_norm = _normalize_for_hash(it.get("venue", ""))
        date_part = it.get("date", "")
        time_part = it.get("time") or ""  # None→空

        key = f"{date_part}|{time_part}|{title_norm}|{venue_norm}"
        h = sha1(key)
        if h in seen:
            continue
        seen.add(h)

        out.append({
            "schema_version": SCHEMA_VERSION,
            **it,  # date / time / title / venue
            "source": BASE_URL,
            "hash": h,
            "extracted_at": extracted_at,
        })

    # 5) 並び替え（date, time(欠損は"99:99"で末尾), title）
    def _sort_key(ev: Dict):
        t = ev.get("time")
        tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
        return (ev.get("date", ""), tkey, ev.get("title", ""))

    out.sort(key=_sort_key)

    # 6) JSON保存（storage/{target_date}_a.json）— Ver.2.0: 全期間データを保存
    path = _storage_path(target_date, "a")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 7) Supabase投入（Ver.2.0用・新機能）
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
        # 失敗時はファイル非生成（推奨）。ログのみを1行で残す。
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\" url=\"{BASE_URL}\"")
        time.sleep(1)  # 他ステップへの影響を減らすための軽い間（任意）
