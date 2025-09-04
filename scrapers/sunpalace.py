# scrapers/sunpalace.py - 福岡サンパレス イベントスクレイパー
import os
import re
import sys
import json
import time
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup

from event_notify.utils.parser import split_and_normalize, JST

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

# --- 日付処理（parser.py対応版）-------------------------------------------
def extract_month_from_header(header_text: str) -> Optional[int]:
    """
    ヘッダーテキストから月を抽出
    例: "2025年7月のイベント情報" -> 7
    """
    if not header_text:
        return None
        
    match = re.search(r'(\d{4})年(\d+)月', header_text)
    if match:
        return int(match.group(2))
    
    # 年なしパターン
    match = re.search(r'(\d+)月', header_text)
    if match:
        return int(match.group(1))
    
    return None

def convert_sunpalace_date_format(date_str: str, month: int, year: int) -> str:
    """
    サンパレス形式を parser.py が理解できる形式に変換
    "5(土)" -> "7.5(土)" (月を補完)
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

# --- スクレイピング -----------------------------------------------------
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

def extract_events_from_table(table, current_month: int, current_year: int) -> List[Dict[str, Any]]:
    """テーブルからイベント情報を抽出（parser.py使用版）"""
    events = []
    
    rows = table.find_all('tr')
    for row in rows[1:]:  # ヘッダー行をスキップ
        cells = row.find_all(['td', 'th'])
        if len(cells) < 4:  # 最低限の列数チェック
            continue
            
        try:
            # セル内容を取得
            date_cell = cells[0].get_text(strip=True) if cells[0] else ""
            event_cell = cells[1].get_text(strip=True) if len(cells) > 1 and cells[1] else ""
            contact_cell = cells[2].get_text(strip=True) if len(cells) > 2 and cells[2] else ""
            open_time = cells[3].get_text(strip=True) if len(cells) > 3 and cells[3] else ""
            start_time = cells[4].get_text(strip=True) if len(cells) > 4 and cells[4] else ""
            
            # イベント名チェック
            if not event_cell or len(event_cell.strip()) == 0:
                continue
            
            # 日付を parser.py が理解できる形式に変換
            converted_date = convert_sunpalace_date_format(date_cell, current_month, current_year)
            
            # 時刻情報も含めて datetime 文字列を構築
            time_info = ""
            if start_time:
                time_info = f" {start_time}"
            elif open_time:
                time_info = f" {open_time}"
            
            datetime_str = f"{converted_date}{time_info}"
            
            # parser.py を使用して正規化・展開
            parsed_events = split_and_normalize(datetime_str, event_cell, VENUE_NAME, current_year)
            
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
                
        except Exception as e:
            print(f"[sunpalace][WARN] Failed to parse row: {e}")
            continue
    
    return events

def scrape_events() -> List[Dict[str, Any]]:
    """サンパレスのイベント情報をスクレイピング"""
    soup = fetch_page()
    all_events = []
    current_year = datetime.now(JST).year
    
    # イベント情報を含むテーブルを検索
    tables = soup.find_all('table')
    
    for table in tables:
        # テーブルの前にある月情報を探す
        month = None
        
        # テーブルの直前の要素から月を探す
        prev_elements = []
        current = table.previous_sibling
        for _ in range(10):  # 最大10個前まで遡る
            if current is None:
                break
            if hasattr(current, 'get_text'):
                prev_elements.append(current.get_text())
            current = current.previous_sibling
        
        # 前の要素から月を抽出
        for elem_text in prev_elements:
            month = extract_month_from_header(elem_text)
            if month:
                break
        
        # デフォルトで現在の月を使用
        if not month:
            month = datetime.now(JST).month
        
        # テーブルからイベントを抽出
        try:
            events = extract_events_from_table(table, month, current_year)
            all_events.extend(events)
        except Exception as e:
            print(f"[sunpalace][WARN] Failed to parse table: {e}")
            continue
    
    return all_events

def filter_today_only(events: List[Dict[str, Any]], target_date: str) -> List[Dict[str, Any]]:
    """今日のイベントのみをフィルタ"""
    return [event for event in events if event.get("date") == target_date]

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
        
        # スクレイピング実行
        all_events = scrape_events()
        print(f"[sunpalace] scraped {len(all_events)} total events")
        
        # 当日分のみフィルタ
        include_future = os.getenv("SCRAPER_INCLUDE_FUTURE") == "1"
        if include_future:
            events_today = all_events
            print(f"[sunpalace] including future events")
        else:
            events_today = filter_today_only(all_events, target_date)
            print(f"[sunpalace] filtered to {len(events_today)} events for {target_date}")
        
        # 重複排除（parser.pyで処理済みだが念のため）
        seen_hashes = set()
        unique_events = []
        for event in events_today:
            event_hash = event.get("hash")
            if event_hash and event_hash not in seen_hashes:
                seen_hashes.add(event_hash)
                unique_events.append(event)
        
        print(f"[sunpalace] after deduplication: {len(unique_events)} events")
        
        # 保存
        save_to_storage(unique_events, target_date)
        
        # 実行時間計算
        elapsed_ms = int((time.time() - start_time) * 1000)
        print(f"[sunpalace] date={target_date} items={len(unique_events)} ms={elapsed_ms} url=\"{TARGET_URL}\"")
        
    except requests.RequestException as e:
        print(f"[sunpalace][ERROR] Network error: {e}")
        sys.exit(0)  # 他のスクレイパーに影響させない
    except Exception as e:
        print(f"[sunpalace][ERROR] Unexpected error: {e}")
        sys.exit(0)

if __name__ == "__main__":
    main()
