# scrapers/paypay_dome_events.py Ver.2.0 + 年跨ぎ対応 + DB投入機能
import os
import json
import time
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# parser.pyから必要な機能をインポート
from event_notify.utils.parser import split_and_normalize, JST

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
    "name": "paypay_dome_events",
    "venue": "みずほPayPayドーム",
    "url_template": "https://www.softbankhawks.co.jp/stadium/event_schedule/{year}/",
    "schema_version": "1.0",
    "selector_profile": "structured HTML with date/event pairs; multi-year URL support",
}
VENUE = META["venue"]
SCHEMA_VERSION = META["schema_version"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EventBot/1.0; +https://example.com/contact)"
}

# ---- UTILS ------------------------------------------------------------------
def _storage_path(date_str: str, code: str) -> Path:
    """共通のストレージパス生成（他のスクレイパーと統一）"""
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
      - 引用符ゆれを統一
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

def parse_paypay_date(date_str: str) -> str:
    """
    "2025/9/13（土）" → "2025-09-13"
    """
    # 基本パターン: 2025/9/13
    match = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})（.+）', date_str.strip())
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return None

def extract_event_time(time_str: str) -> str:
    """
    PayPayドーム固有の時刻抽出:
    "開催時間 11:00～19:00" → "11:00"
    "開演時間 開場 16:00 開演 18:00" → "18:00"
    """
    if not time_str:
        return None
    
    # パターン1: 開催時間 11:00～19:00（開始時刻を抽出）
    schedule_match = re.search(r'開催時間\s*(\d{1,2}:\d{2})', time_str)
    if schedule_match:
        return schedule_match.group(1)
    
    # パターン2: 開演時間 開場 XX:XX 開演 YY:YY（開演優先）
    start_match = re.search(r'開演\s*(\d{1,2}:\d{2})', time_str)
    if start_match:
        return start_match.group(1)
    
    # パターン3: 開場時刻のみ
    open_match = re.search(r'開場\s*(\d{1,2}:\d{2})', time_str)
    if open_match:
        return open_match.group(1)
    
    # パターン4: 一般的な時刻パターン（HH:MM）
    time_match = re.search(r'(\d{1,2}:\d{2})', time_str)
    if time_match:
        return time_match.group(1)
    
    return None  # 時刻未定

def extract_event_title(title_str: str) -> str:
    """
    "[acosta!@みずほPayPayドーム福岡](https://acosta.jp/...)" 
    → "acosta!@みずほPayPayドーム福岡"
    """
    # [タイトル](URL) パターンから抽出
    match = re.search(r'\[([^\]]+)\]', title_str)
    if match:
        return match.group(1).strip()
    
    # マークダウンリンクでない場合はそのまま返す
    return title_str.strip()

# ---- SCRAPING ---------------------------------------------------------------
def fetch_year_events(url: str, year: int) -> List[Dict]:
    """指定年のPayPayドームイベント情報を取得"""
    try:
        print(f"[{META['name']}] Fetching {year} from {url}")
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        print(f"[DEBUG] HTTP Status: {r.status_code}")
        print(f"[DEBUG] Content length: {len(r.text)}")
        
        events = []
        
        # 正しいHTML構造に基づく抽出
        # dl.temp_calendarList > dt（日付）+ dd（詳細）のペア
        calendar_lists = soup.find_all('dl', class_='temp_calendarList')
        print(f"[DEBUG] Found {len(calendar_lists)} calendar lists for {year}")
        
        for calendar in calendar_lists:
            # dt（日付）とdd（詳細）のペアを処理
            dt_elements = calendar.find_all('dt')
            dd_elements = calendar.find_all('dd')
            
            print(f"[DEBUG] Found {len(dt_elements)} dates and {len(dd_elements)} details")
            
            # dtとddのペアを処理
            for dt, dd in zip(dt_elements, dd_elements):
                date_text = dt.get_text().strip()
                print(f"[DEBUG] Processing date: {date_text}")
                
                # 日付パターンの確認
                if not re.match(r'\d{4}/\d{1,2}/\d{1,2}（.+）', date_text):
                    print(f"[DEBUG] Date pattern not matched: {date_text}")
                    continue
                
                # table内からイベント情報を抽出
                table = dd.find('table')
                if not table:
                    print(f"[DEBUG] No table found for date: {date_text}")
                    continue
                
                event_title = None
                event_time = None
                
                # tableの行を解析
                rows = table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    
                    if not th or not td:
                        continue
                    
                    th_text = th.get_text().strip()
                    td_text = td.get_text().strip()
                    
                    if th_text == 'イベント':
                        # span要素があればその中身、なければtd全体
                        span = td.find('span')
                        event_title = span.get_text().strip() if span else td_text
                        
                    elif th_text in ['開催時間', '開演時間']:
                        event_time = td_text
                
                if event_title:
                    print(f"[DEBUG] Found event: {date_text} | {event_title} | {event_time}")
                    events.append({
                        "date_raw": date_text,
                        "title_raw": event_title,
                        "time_raw": event_time or "",
                        "source_year": year
                    })
                else:
                    print(f"[DEBUG] No event title found for date: {date_text}")
        
        print(f"[DEBUG] Total events extracted from {year}: {len(events)}")
        return events
        
    except requests.RequestException as e:
        print(f"[{META['name']}] Failed to fetch {year}: HTTP error: {e}")
        return []
    except Exception as e:
        print(f"[{META['name']}] Failed to fetch {year}: {e}")
        return []

def fetch_multi_year_events() -> List[Dict]:
    """年跨ぎ対応: 必要に応じて複数年のイベント情報を取得"""
    start_date, end_date = get_target_date_range()
    
    # 開始年と終了年を判定
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    
    print(f"[{META['name']}] Target range: {start_date} ~ {end_date} (years: {start_year}~{end_year})")
    
    all_events = []
    
    # 必要な年のURLを取得
    for year in range(start_year, end_year + 1):
        url = META["url_template"].format(year=year)
        year_events = fetch_year_events(url, year)
        all_events.extend(year_events)
    
    return all_events

def normalize_events(raw_events: List[Dict]) -> List[Dict]:
    """生データを正規化してevent_notify形式に変換（PayPayドーム専用処理）"""
    normalized = []
    
    for raw in raw_events:
        # 日付正規化: "2025/9/13（土）" → "2025-09-13"
        date = parse_paypay_date(raw["date_raw"])
        if not date:
            continue
        
        # 時刻抽出: "開催時間 11:00～19:00" → "11:00"
        time_extracted = extract_event_time(raw["time_raw"])
        
        # タイトル抽出
        title = extract_event_title(raw["title_raw"])
        
        normalized.append({
            "date": date,
            "time": time_extracted,
            "title": title,
            "venue": VENUE,
            "event_type": "event"  # 野球と区別
        })
    
    return normalized

# ---- MAIN -------------------------------------------------------------------
def main():
    t0 = time.time()

    target_date = resolve_target_date()
    
    print(f"[{META['name']}] target_date={target_date}")

    # 1) 全期間データ取得（年跨ぎ対応）
    raw = fetch_multi_year_events()
    print(f"[{META['name']}] scraped {len(raw)} total events")

    # 2) 正規化
    normalized = normalize_events(raw)
    print(f"[{META['name']}] normalized to {len(normalized)} events")

    # 期間範囲計算（当月1日～翌月末日）
    start_date, end_date = get_target_date_range()
    print(f"[{META['name']}] Target range: {start_date} ~ {end_date}")

    # 3) 期間フィルタリング（当月1日～翌月末日）
    items = filter_date_range(normalized, start_date, end_date)
    print(f"[{META['name']}] filtered to {len(items)} events for {start_date} ~ {end_date}")

    # 4) 重複排除＆メタ付与（全期間データ - Ver.2.0用）
    seen = set()
    out: List[Dict] = []
    extracted_at = datetime.now(JST).isoformat()

    for it in items:
        title_norm = _normalize_for_hash(it.get("title", ""))
        venue_norm = _normalize_for_hash(it.get("venue", ""))
        date_part = it.get("date", "")
        time_part = it.get("time") or ""

        key = f"{date_part}|{time_part}|{title_norm}|{venue_norm}"
        h = sha1(key)
        if h in seen:
            continue
        seen.add(h)

        # 年跨ぎ対応でsource URLを動的生成
        event_year = int(date_part[:4])
        source_url = META["url_template"].format(year=event_year)

        out.append({
            "schema_version": SCHEMA_VERSION,
            **it,
            "source": source_url,
            "hash": h,
            "extracted_at": extracted_at,
        })

    # 5) 並び替え
    def _sort_key(ev: Dict):
        t = ev.get("time")
        tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
        return (ev.get("date", ""), tkey, ev.get("title", ""))

    out.sort(key=_sort_key)

    # 6) JSON保存（storage/{target_date}_f_event.json）— Ver.2.0: 全期間データを保存
    path = _storage_path(target_date, "f_event")
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
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\"")
        time.sleep(1)
