# scrapers/marinemesse_b.py Ver.2.0 + DB投入機能
import os
import json
import time
import re
import unicodedata
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from event_notify.utils.parser import split_and_normalize, JST

# Supabase投入用（オプション）
try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    load_dotenv()
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

DEBUG = os.getenv("DEBUG_B", "0") == "1"

BASE_URL = "https://www.marinemesse.or.jp/messe-b/event/"
VENUE = "マリンメッセB館"
VENUE_CODE = "b"
SCHEMA_VERSION = "1.0"

HEADERS = {
    "User-Agent": "event_notify/1.0 (+https://example.com; contact=email@example.com)"
}

# セレクタを一元管理（優先→代替）
SELECTORS = {
    "table_primary": "table.table_list01",
    "table_fallback": "table",
    "title_anchor": "a",
    "th_like": "th, dt, .label, .ttl",
}

REQUEST_TIMEOUT = 15
RETRY_5XX = 3
RETRY_SLEEP_BASE = 1.0
DETAIL_REQUEST_SLEEP = 1.0

# ---- META ----------------------------------------------------------------
META = {
    "name": "marinemesse_b",
    "venue": VENUE,
    "url": BASE_URL,
}

def sha1(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _storage_path(date_str: str, code: str) -> Path:
    """共通のストレージパス生成"""
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"

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

def _http_get(url: str, session: requests.Session) -> requests.Response:
    """5xxに対する指数バックオフ付きGET"""
    for i in range(RETRY_5XX + 1):
        r = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if 500 <= r.status_code < 600 and i < RETRY_5XX:
            time.sleep(RETRY_SLEEP_BASE * (2 ** i))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r

def _extract_datetime_from_detail(url: str, session: requests.Session) -> str:
    """詳細ページから開催日時テキストを抽出し1本に束ねて返す"""
    try:
        time.sleep(DETAIL_REQUEST_SLEEP)
        r = _http_get(url, session)
        s = BeautifulSoup(r.text, "html.parser")

        # 優先: 「開催日時」「開催日」「日程」などの th/label を探す
        for th in s.select(SELECTORS["th_like"]):
            label = th.get_text(" ", strip=True)
            if any(k in label for k in ["開催日時", "開催日", "日程", "日時"]):
                td = th.find_next("td") or th.find_next("dd") or th.parent.find_next("td")
                if td:
                    text = td.get_text(" ", strip=True)
                    if text:
                        return re.sub(r"\s+", " ", text)

        # 次善: ページ全体から日付らしい行を拾う
        body_text = s.get_text(" ", strip=True)
        m = re.search(r"(\d{4}[./-]\d{1,2}[./-]\d{1,2}[^。\n]*?)", body_text)
        if m:
            return m.group(1)
        m2 = re.search(r"(\d{1,2}[./]\d{1,2}.*?(?:\d{1,2}:\d{2})?.*?)", body_text)
        if m2:
            return m2.group(1)

    except Exception as e:
        if DEBUG:
            print("[marinemesse_b][ERROR] detail:", repr(e))
    return ""

def fetch_month_events(url: str, year: int, month: int, session: requests.Session) -> List[Dict[str, str]]:
    """指定月のイベントを取得（B館の複雑な構造対応）"""
    try:
        r = _http_get(url, session)
        soup = BeautifulSoup(r.text, "html.parser")

        table = soup.select_one(SELECTORS["table_primary"]) or soup.select_one(SELECTORS["table_fallback"])
        if not table:
            return []

        events = []
        pending_datetime_lines: List[str] = []

        for tr in table.select("tr"):
            if tr.find("th"):
                continue
            tds = tr.find_all("td")
            if not tds:
                continue

            a = tr.select_one(SELECTORS["title_anchor"])
            if a and a.get_text(strip=True):
                title = a.get_text(" ", strip=True)

                # 直前まで貯めた日時テキストを束ねる
                datetime_text = " ".join(s for s in (t.strip() for t in pending_datetime_lines) if s)
                pending_datetime_lines = []

                # 当行1列目も Fallback
                if not datetime_text and tds:
                    datetime_text = tds[0].get_text(" ", strip=True)

                # さらに空なら詳細ページ
                href = a.get("href")
                if href and href.startswith("/"):
                    href = f"https://www.marinemesse.or.jp{href}"
                if not datetime_text and href:
                    dt_from_detail = _extract_datetime_from_detail(href, session)
                    if dt_from_detail:
                        datetime_text = dt_from_detail

                events.append({
                    "datetime": datetime_text, 
                    "title": title,
                    "source_month": f"{year}-{month:02d}"
                })
                continue

            first_col_text = tds[0].get_text(" ", strip=True) if tds else ""
            if first_col_text:
                pending_datetime_lines.append(first_col_text)

        return events

    except Exception as e:
        print(f"[marinemesse_b] Failed to fetch {year}-{month:02d}: {e}")
        return []

def fetch_multi_month_events(session: requests.Session) -> List[Dict[str, str]]:
    """当月1日～翌月末日の2ヶ月分を取得"""
    all_events = []
    current_month = datetime.now(JST).replace(day=1)
    
    # 当月+翌月の2ヶ月分
    for i in range(2):
        target = current_month + relativedelta(months=i)
        url = f"{BASE_URL}?yy={target.year}&mm={target.month}"
        
        print(f"[marinemesse_b] Fetching {target.year}-{target.month:02d} from {url}")
        month_events = fetch_month_events(url, target.year, target.month, session)
        all_events.extend(month_events)
    
    return all_events

def main():
    t0 = time.time()
    session = requests.Session()

    target_date = _resolve_target_date()

    # Ver.2.0: 常に2ヶ月分取得
    raw = fetch_multi_month_events(session)
    
    # 期間範囲計算（当月1日～翌月末日）
    start_date, end_date = get_target_date_range()
    print(f"[marinemesse_b] Target range: {start_date} ~ {end_date}")

    # 正規化＆展開
    normalized: List[Dict[str, Any]] = []
    for e in raw:
        normalized.extend(split_and_normalize(e["datetime"], e["title"], VENUE))

    # 期間フィルタリング（当月1日～翌月末日）
    all_events = filter_date_range(normalized, start_date, end_date)

    # ハッシュ付与（全期間データ - Ver.2.0用）
    out: List[Dict[str, Any]] = []
    seen = set()
    extracted_at = datetime.now(JST).isoformat()
    
    for it in all_events:
        title_norm = _normalize_for_hash(it.get("title", ""))
        venue_norm = _normalize_for_hash(it.get("venue", ""))
        date_part = it.get("date", "")
        time_part = it.get("time") or ""

        key = f"{date_part}|{time_part}|{title_norm}|{venue_norm}"
        h = sha1(key)
        if h in seen:
            continue
        seen.add(h)

        out.append({
            "schema_version": SCHEMA_VERSION,
            **it,
            "source": BASE_URL,
            "hash": h,
            "extracted_at": extracted_at,
        })

    # 並び替え（date, time(欠損は"99:99"で末尾), title）
    def _sort_key(ev: Dict):
        t = ev.get("time")
        tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
        return (ev.get("date", ""), tkey, ev.get("title", ""))

    out.sort(key=_sort_key)

    # JSON保存（storage/{target_date}_b.json）— Ver.2.0: 全期間データを保存
    path = _storage_path(target_date, VENUE_CODE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Supabase投入（Ver.2.0用・新機能）
    db_enabled = os.getenv("ENABLE_DB_SAVE", "0") == "1"
    if db_enabled and SUPABASE_AVAILABLE:
        save_to_supabase(out)
    elif db_enabled:
        print(f"[{META['name']}] DB投入スキップ: Supabase依存関係不足")

    ms = int((time.time() - t0) * 1000)
    print(f"[marinemesse_b] date={target_date} items={len(out)} range={start_date}~{end_date} ms={ms} → {path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 失敗時も"壊れない"を優先し、空配列を書き出して可観測化
        try:
            target_date = _resolve_target_date()
            path = _storage_path(target_date, VENUE_CODE)
            with open(path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print(f"[marinemesse_b][ERROR] {repr(e)} -> wrote empty file {path}")
        except Exception as e2:
            print(f"[marinemesse_b][FATAL] fallback write failed: {repr(e2)}")
