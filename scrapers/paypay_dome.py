# scrapers/sunpalace.py Ver.2.0 + DB投入機能
import os
import re
import sys
import json
import time
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
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

# --- 設定 ---------------------------------------------------------------
TARGET_URL = "https://www.f-sunpalace.com/hall/#hallEvent"
VENUE_NAME = "福岡サンパレス"
VENUE_CODE = "e"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- ユーティリティ ------------------------------------------------------
def _storage_path(date_str: str, code: str) -> Path:
    """共通のストレージパス生成（他のスクレイパーと統一）"""
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"

def determine_today() -> str:
    """環境変数または現在日時から対象日を決定"""
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

def normalize_text(text: str) -> str:
    """テキスト正規化"""
    if not text:
        return ""
    
    # NFKC正規化
    import unicodedata
    text = unicodedata.normalize("NFKC", text)
    
    # 空白圧縮・トリム
    text = re.sub(r'\s+', ' ', text.strip())
    
    # 引用符統一
    text = text.replace('"', '"').replace('"', '"').replace("'", "'").replace("'", "'")
    
    # 波ダッシュ統一
    text = text.replace('〜', '～').replace('－', '−').replace('―', '−')
    
    return text

def create_hash(date: str, time: str, title: str, venue: str) -> str:
    """重複排除用ハッシュ生成"""
    key = f"{date}|{time or ''}|{normalize_text(title)}|{normalize_text(venue)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()

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
        print(f"[sunpalace] DB投入: データなし")
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
        
        print(f"[sunpalace] DB投入成功: {len(result.data)}件")
        
    except Exception as e:
        print(f"[sunpalace][ERROR] DB投入失敗: {e}")
        # JSON保存は継続（DB失敗は致命的ではない）

# --- 月別セクション分離（修正版）-------------------------------------------
def extract_month_sections(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    月別セクションを正確に分離して取得
    返値: [{"month": 9, "year": 2025, "table": table_element}, ...]
    """
    sections = []
    current_year = datetime.now(JST).year
    
    # 月ヘッダーのパターン
    month_pattern = re.compile(r'(\d{4})年(\d+)月のイベント情報|(\d+)月のイベント情報')
    
    # ページ内の全要素を順番に走査
    all_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'table'])
    
    current_month = None
    current_year_for_section = current_year
    
    for element in all_elements:
        element_text = element.get_text(strip=True)
        
        # 月ヘッダーを検出
        month_match = month_pattern.search(element_text)
        if month_match:
            if month_match.group(1):  # 年月両方指定
                current_year_for_section = int(month_match.group(1))
                current_month = int(month_match.group(2))
            else:  # 月のみ指定
                current_month = int(month_match.group(3))
            
            print(f"[sunpalace] Found month section: {current_year_for_section}年{current_month}月")
            continue
        
        # テーブル要素でかつ月が設定されている場合
        if element.name == 'table' and current_month is not None:
            # テーブルがイベント情報を含むかチェック
            if has_event_content(element):
                sections.append({
                    "month": current_month,
                    "year": current_year_for_section,
                    "table": element
                })
                print(f"[sunpalace] Added table for {current_year_for_section}-{current_month:02d}")
    
    return sections

def has_event_content(table) -> bool:
    """テーブルがイベント情報を含むかチェック"""
    if not table:
        return False
    
    # ヘッダー行をチェック
    first_row = table.find('tr')
    if not first_row:
        return False
    
    header_text = first_row.get_text().lower()
    # イベント情報テーブルの特徴的なヘッダーをチェック
    event_keywords = ['開催日', 'イベント', '主催者', '開場', '開演', '入場料']
    return any(keyword in header_text for keyword in event_keywords)

def convert_sunpalace_date_format(date_str: str, month: int, year: int) -> str:
    """
    サンパレス形式を parser.py が理解できる形式に変換
    "5(土)" -> "9.5(土)" (月を補完)
    """
    if not date_str:
        return ""
        
    # 既に月が含まれている場合はそのまま
    if re.match(r'\d+\.\d+', date_str):
        return date_str
        
    # 日付のみの場合は月を補完
    match = re.match(r'^(\d+)(\([^)]+\))?', date_str.strip())
    if match:
        day = match.group(1)
        weekday = match.group(2) or ""
        return f"{month}.{day}{weekday}"
    
    return date_str

# --- スクレイピング（修正版）--------------------------------------------
def fetch_page() -> BeautifulSoup:
    """Webページを取得してパース"""
    try:
        response = requests.get(TARGET_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
        
    except requests.RequestException as e:
        print(f"[sunpalace][ERROR] Failed to fetch {TARGET_URL}: {e}")
        raise

def extract_events_from_table(table, target_month: int, target_year: int) -> List[Dict[str, Any]]:
    """指定された月のテーブルからイベント情報を抽出（rowspan対応版）"""
    events = []
    
    rows = table.find_all('tr')
    if not rows:
        return events
    
    # rowspan対応のためのカラム継続データ管理
    column_continuations = {}  # {column_index: {"value": "継続する値", "remaining_rows": 残り行数}}
    
    for row_idx, row in enumerate(rows[1:], 1):  # ヘッダー行をスキップ
        cells = row.find_all(['td', 'th'])
        if len(cells) < 1:  # 最低限日付セルがあるかチェック
            continue
            
        try:
            # 実際のカラム値を取得（rowspan考慮）
            actual_columns = []
            cell_idx = 0
            
            for col_idx in range(6):  # 最大6列想定（日付、イベント、主催者、開場、開演、入場料）
                if col_idx in column_continuations:
                    # 前の行から継続
                    cont = column_continuations[col_idx]
                    actual_columns.append(cont["value"])
                    cont["remaining_rows"] -= 1
                    if cont["remaining_rows"] <= 0:
                        del column_continuations[col_idx]
                elif cell_idx < len(cells):
                    # 新しいセルから取得
                    cell = cells[cell_idx]
                    cell_text = cell.get_text(strip=True)
                    actual_columns.append(cell_text)
                    
                    # rowspan チェック
                    rowspan = cell.get('rowspan')
                    if rowspan and int(rowspan) > 1:
                        column_continuations[col_idx] = {
                            "value": cell_text,
                            "remaining_rows": int(rowspan) - 1
                        }
                        print(f"[sunpalace] Found rowspan={rowspan} at column {col_idx}: '{cell_text}'")
                    
                    cell_idx += 1
                else:
                    # セルがない場合は空文字
                    actual_columns.append("")
            
            # 各カラムを変数に割り当て
            date_cell = actual_columns[0] if len(actual_columns) > 0 else ""
            event_cell = actual_columns[1] if len(actual_columns) > 1 else ""
            contact_cell = actual_columns[2] if len(actual_columns) > 2 else ""
            open_time = actual_columns[3] if len(actual_columns) > 3 else ""
            start_time = actual_columns[4] if len(actual_columns) > 4 else ""
            price_cell = actual_columns[5] if len(actual_columns) > 5 else ""
            
            print(f"[sunpalace] Row {row_idx}: date='{date_cell}', event='{event_cell}', open='{open_time}', start='{start_time}'")
            
            # イベント名チェック
            if not event_cell or len(event_cell.strip()) == 0:
                print(f"[sunpalace] Row {row_idx}: Skipping - no event name")
                continue
            
            # 日付チェック
            if not date_cell or len(date_cell.strip()) == 0:
                print(f"[sunpalace] Row {row_idx}: Skipping - no date")
                continue
            
            # 日付を parser.py が理解できる形式に変換
            converted_date = convert_sunpalace_date_format(date_cell, target_month, target_year)
            
            # 複数時刻の処理（br区切り対応）
            open_times = [t.strip() for t in open_time.replace('<br>', '\n').split('\n') if t.strip()] if open_time else []
            start_times = [t.strip() for t in start_time.replace('<br>', '\n').split('\n') if t.strip()] if start_time else []
            
            # 開演時刻を優先、なければ開場時刻
            if start_times:
                time_list = start_times
            elif open_times:
                time_list = open_times
            else:
                time_list = [""]
            
            # 各時刻でイベントを生成
            for time_str in time_list:
                datetime_str = f"{converted_date}"
                if time_str:
                    datetime_str += f" {time_str}"
                
                print(f"[sunpalace] Processing: month={target_month}, date_cell='{date_cell}' -> converted='{converted_date}' -> datetime_str='{datetime_str}'")
                
                # parser.py を使用して正規化・展開
                parsed_events = split_and_normalize(datetime_str, event_cell, VENUE_NAME, target_year)
                
                for parsed_event in parsed_events:
                    # メタデータ追加
                    event = {
                        "schema_version": "1.0",
                        **parsed_event,
                        "source": TARGET_URL,
                        "extracted_at": datetime.now(JST).isoformat(),
                    }
                    
                    # ハッシュ生成
                    event["hash"] = create_hash(
                        event["date"],
                        event.get("time", "") or "",
                        event["title"],
                        event["venue"]
                    )
                    
                    events.append(event)
                    print(f"[sunpalace] Added event: {event['date']} {event.get('time', 'N/A')} - {event['title']}")
                
        except Exception as e:
            print(f"[sunpalace][WARN] Failed to parse row {row_idx}: {e}")
            continue
    
    return events

def scrape_events() -> List[Dict[str, Any]]:
    """サンパレスのイベント情報をスクレイピング（修正版）"""
    soup = fetch_page()
    all_events = []
    
    # 月別セクションを正確に分離
    month_sections = extract_month_sections(soup)
    
    if not month_sections:
        print("[sunpalace][WARN] No month sections found")
        return []
    
    # 各月のセクションを処理
    for section in month_sections:
        month = section["month"]
        year = section["year"]
        table = section["table"]
        
        print(f"[sunpalace] Processing {year}-{month:02d} section")
        
        try:
            events = extract_events_from_table(table, month, year)
            all_events.extend(events)
            print(f"[sunpalace] Extracted {len(events)} events from {year}-{month:02d}")
        except Exception as e:
            print(f"[sunpalace][WARN] Failed to parse {year}-{month:02d} section: {e}")
            continue
    
    return all_events

def save_to_storage(events: List[Dict[str, Any]], target_date: str) -> None:
    """ストレージにJSONとして保存"""
    file_path = _storage_path(target_date, VENUE_CODE)
    
    try:
        # 整列（日付、時刻、タイトル順）
        events.sort(key=lambda x: (
            x.get("date", ""),
            x.get("time") or "99:99",
            x.get("title", "")
        ))
        
        # JSON保存
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
            
        print(f"[sunpalace] date={target_date} items={len(events)} saved to {file_path}")
        
    except Exception as e:
        print(f"[sunpalace][ERROR] Failed to save events: {e}")
        raise

# --- メイン処理 ---------------------------------------------------------
def main():
    """メイン処理"""
    start_time = time.time()
    
    try:
        # 対象日決定
        target_date = determine_today()
        print(f"[sunpalace] target_date={target_date}")
        
        # スクレイピング実行（全期間）
        all_events = scrape_events()
        print(f"[sunpalace] scraped {len(all_events)} total events")
        
        # 期間範囲計算（当月1日～翌月末日）
        start_date, end_date = get_target_date_range()
        print(f"[sunpalace] Target range: {start_date} ~ {end_date}")

        # 期間フィルタリング（当月1日～翌月末日）
        events_filtered = filter_date_range(all_events, start_date, end_date)
        print(f"[sunpalace] filtered to {len(events_filtered)} events for {start_date} ~ {end_date}")
        
        # 重複排除（parser.pyで処理済みだが念のため）
        seen_hashes = set()
        unique_events = []
        for event in events_filtered:
            event_hash = event.get("hash")
            if event_hash and event_hash not in seen_hashes:
                seen_hashes.add(event_hash)
                unique_events.append(event)
        
        print(f"[sunpalace] after deduplication: {len(unique_events)} events")
        
        # 保存
        save_to_storage(unique_events, target_date)
        
        # Supabase投入（Ver.2.0用・新機能）
        db_enabled = os.getenv("ENABLE_DB_SAVE", "0") == "1"
        if db_enabled and SUPABASE_AVAILABLE:
            save_to_supabase(unique_events)
        elif db_enabled:
            print(f"[sunpalace] DB投入スキップ: Supabase依存関係不足")
        
        # 実行時間計算
        elapsed_ms = int((time.time() - start_time) * 1000)
        print(f"[sunpalace] date={target_date} items={len(unique_events)} range={start_date}~{end_date} ms={elapsed_ms} url=\"{TARGET_URL}\"")
        
    except requests.RequestException as e:
        print(f"[sunpalace][ERROR] Network error: {e}")
        sys.exit(0)  # 他のスクレイパーに影響させない
    except Exception as e:
        print(f"[sunpalace][ERROR] Unexpected error: {e}")
        sys.exit(0)

if __name__ == "__main__":
    main()
