# scrapers/sunpalace.py Ver.3.0 — HPリニューアル対応 (ul.schedule_table > li)
import os
import re
import sys
import json
import time
import hashlib
import unicodedata
import requests
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup

from utils.parser import JST

# Supabase投入用（オプション）
try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    load_dotenv()
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# --- 設定 ---------------------------------------------------------------
META = {
    "name": "sunpalace",
    "venue": "福岡サンパレス",
    "code": "e",
    "base_url": "https://www.f-sunpalace.com/hall/",
    "schema_version": "1.0",
}
VENUE = META["venue"]
VENUE_CODE = META["code"]
SCHEMA_VERSION = META["schema_version"]
BASE_URL = META["base_url"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 開演時刻を抽出する正規表現（「開演HH:MM」「開演★HH:MM」など）
_TIME_RE = re.compile(r'(\d{1,2}):(\d{2})')

# --- ユーティリティ ------------------------------------------------------
def _storage_path(date_str: str, code: str) -> Path:
    """共通のストレージパス生成（他のスクレイパーと統一）"""
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"


def resolve_target_date() -> str:
    """環境変数でターゲット日付を上書き可能（YYYY-MM-DD）。未指定ならJST今日"""
    override = os.getenv("SCRAPER_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")


def get_target_date_range() -> tuple[str, str]:
    """当月1日～翌月末日の期間を取得"""
    today = datetime.now(JST)
    start_date = today.replace(day=1)
    next_month_first = start_date + relativedelta(months=1)
    end_date = next_month_first + relativedelta(months=1) - timedelta(days=1)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def filter_date_range(items: List[Dict], start_date: str, end_date: str) -> List[Dict]:
    """指定期間内のイベントのみ抽出"""
    return [e for e in items if start_date <= e.get("date", "") <= end_date]


def _normalize_for_hash(s: str) -> str:
    """ハッシュ用の軽量正規化"""
    if s is None:
        return ""
    x = unicodedata.normalize("NFKC", s)
    x = x.replace("\u201c", '"').replace("\u201d", '"').replace("\u201f", '"')
    x = x.replace("\u2018", "'").replace("\u2019", "'")
    x = x.replace('〜', '～').replace('－', '−').replace('―', '−')
    x = re.sub(r"\s+", " ", x).strip()
    return x


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _normalize_title(text: str) -> str:
    """タイトルテキストの正規化（改行→スペース、連続空白圧縮）"""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def _extract_start_times(starting_text: str) -> List[Optional[str]]:
    """
    p.starting のテキストから開演時刻を抽出。
    例: "開演17:30"        → ["17:30"]
        "開演12:30開演18:00" → ["12:30", "18:00"]
        "開演★12:30開演18:00" → ["12:30", "18:00"]
        "-"                → [None]
    """
    if not starting_text or starting_text.strip() == '-':
        return [None]

    times = []
    for m in _TIME_RE.finditer(starting_text):
        hh, mi = int(m.group(1)), int(m.group(2))
        if 0 <= hh <= 23 and 0 <= mi <= 59:
            times.append(f"{hh:02d}:{mi:02d}")

    return times if times else [None]


# --- Supabase -----------------------------------------------------------
def get_supabase_client() -> Client:
    if not SUPABASE_AVAILABLE:
        raise RuntimeError("Supabase依存関係が不足: pip install supabase python-dotenv")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("環境変数 SUPABASE_URL, SUPABASE_KEY が設定されていません")
    return create_client(url, key)


def save_to_supabase(events: List[Dict]) -> None:
    if not events:
        print(f"[{META['name']}] DB投入: データなし")
        return
    try:
        supabase = get_supabase_client()
        db_records = []
        for event in events:
            record = {
                "date": event.get("date"),
                "time": event.get("time"),
                "title": event.get("title", ""),
                "venue": event.get("venue", ""),
                "source_url": event.get("source", ""),
                "data_hash": event.get("hash", ""),
                "event_type": "auto",
                "notes": event.get("notes"),
            }
            db_records.append(record)
        result = supabase.table('events').upsert(
            db_records, on_conflict="data_hash"
        ).execute()
        print(f"[{META['name']}] DB投入成功: {len(result.data)}件")
    except Exception as e:
        print(f"[{META['name']}][ERROR] DB投入失敗: {e}")


# --- スクレイピング（新HTML構造対応）--------------------------------------
def build_month_url(year: int, month: int) -> str:
    """月別スケジュールページURLを生成"""
    return f"{BASE_URL}?ym={year}-{month:02d}#schedule"


def fetch_month_events(year: int, month: int) -> List[Dict]:
    """
    指定月のスケジュールページを取得し、イベントを抽出。
    新HTML構造: ul.schedule_table > li
    """
    url = build_month_url(year, month)
    print(f"[{META['name']}] Fetching {year}-{month:02d} from {url}")

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
    except requests.RequestException as e:
        print(f"[{META['name']}][ERROR] Failed to fetch {url}: {e}")
        return []

    events = []
    schedule_list = soup.select('ul.schedule_table > li')

    if not schedule_list:
        print(f"[{META['name']}][WARN] No schedule items found for {year}-{month:02d}")
        return []

    print(f"[{META['name']}] Found {len(schedule_list)} schedule items for {year}-{month:02d}")

    for idx, li in enumerate(schedule_list):
        try:
            # --- 日付 ---
            date_el = li.select_one('p.date span.en')
            if not date_el:
                print(f"[{META['name']}] Item {idx}: Skipping - no date element")
                continue

            day_text = date_el.get_text(strip=True)
            day_match = re.match(r'(\d+)', day_text)
            if not day_match:
                print(f"[{META['name']}] Item {idx}: Skipping - invalid day '{day_text}'")
                continue

            day = int(day_match.group(1))
            try:
                event_date = f"{year}-{month:02d}-{day:02d}"
                # 日付の妥当性チェック
                datetime.strptime(event_date, "%Y-%m-%d")
            except ValueError:
                print(f"[{META['name']}] Item {idx}: Skipping - invalid date {event_date}")
                continue

            # --- タイトル ---
            name_el = li.select_one('p.name')
            if not name_el:
                print(f"[{META['name']}] Item {idx}: Skipping - no name element")
                continue

            title = _normalize_title(name_el.get_text())
            if not title:
                print(f"[{META['name']}] Item {idx}: Skipping - empty title")
                continue

            # --- 開演時刻 ---
            starting_el = li.select_one('p.starting')
            starting_text = starting_el.get_text() if starting_el else "-"
            start_times = _extract_start_times(starting_text)

            # --- 複数公演展開 ---
            for t in start_times:
                events.append({
                    "date": event_date,
                    "time": t,
                    "title": title,
                    "source_month": f"{year}-{month:02d}",
                })

            print(f"[{META['name']}] Item {idx}: {event_date} {start_times} - {title[:40]}")

        except Exception as e:
            print(f"[{META['name']}][WARN] Failed to parse item {idx}: {e}")
            continue

    print(f"[{META['name']}] Extracted {len(events)} events from {year}-{month:02d}")
    return events


def fetch_multi_month_events() -> List[Dict]:
    """当月＋翌月の2ヶ月分を取得"""
    all_events = []
    current_month = datetime.now(JST).replace(day=1)

    for i in range(2):
        target = current_month + relativedelta(months=i)
        month_events = fetch_month_events(target.year, target.month)
        all_events.extend(month_events)

    return all_events


# --- メイン処理 ---------------------------------------------------------
def main():
    t0 = time.time()

    target_date = resolve_target_date()
    print(f"[{META['name']}] target_date={target_date}")

    # 1) スクレイピング（2ヶ月分）
    raw = fetch_multi_month_events()
    print(f"[{META['name']}] scraped {len(raw)} total events")

    # 2) 期間範囲計算（当月1日～翌月末日）
    start_date, end_date = get_target_date_range()
    print(f"[{META['name']}] Target range: {start_date} ~ {end_date}")

    # 3) 期間フィルタリング
    filtered = filter_date_range(raw, start_date, end_date)
    print(f"[{META['name']}] filtered to {len(filtered)} events for {start_date} ~ {end_date}")

    # 4) 重複排除＆メタ付与
    seen = set()
    out: List[Dict] = []
    extracted_at = datetime.now(JST).isoformat()

    for it in filtered:
        title_norm = _normalize_for_hash(it.get("title", ""))
        venue_norm = _normalize_for_hash(VENUE)
        date_part = it.get("date", "")
        time_part = it.get("time") or ""

        key = f"{date_part}|{time_part}|{title_norm}|{venue_norm}"
        h = sha1(key)
        if h in seen:
            continue
        seen.add(h)

        out.append({
            "schema_version": SCHEMA_VERSION,
            "date": it["date"],
            "time": it.get("time"),
            "title": it["title"],
            "venue": VENUE,
            "source": BASE_URL,
            "hash": h,
            "extracted_at": extracted_at,
        })

    print(f"[{META['name']}] after deduplication: {len(out)} events")

    # 5) 並び替え（date, time(欠損は"99:99"で末尾), title）
    def _sort_key(ev: Dict):
        t = ev.get("time")
        tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
        return (ev.get("date", ""), tkey, ev.get("title", ""))

    out.sort(key=_sort_key)

    # 6) JSON保存（storage/{target_date}_e.json）
    path = _storage_path(target_date, VENUE_CODE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[{META['name']}] Saved {len(out)} events to {path}")

    # 7) Supabase投入
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
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\" url=\"{BASE_URL}\"")
        time.sleep(1)
