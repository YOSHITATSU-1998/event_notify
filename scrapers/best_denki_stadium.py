# scrapers/best_denki_stadium.py
import os
import json
import time
import re
import unicodedata
from datetime import datetime
from typing import List, Dict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from event_notify.utils.parser import split_and_normalize, JST

# ---- META / SELECTORS -------------------------------------------------------
META = {
    "name": "best_denki_stadium",
    "venue": "ベスト電器スタジアム",
    "url": "https://www.avispa.co.jp/game_practice",
    "schema_version": "1.0",
    "selector_profile": "j1league table with stadium column filtering",
}
URL = META["url"]
VENUE = META["venue"]
SCHEMA_VERSION = META["schema_version"]

SELECTORS = {
    # J1リーグテーブルの行
    "primary": "#j1league table tbody tr",
    # フォールバック: 一般的なテーブル
    "fallback": "table tr",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EventBot/1.0; +https://github.com/your-repo/event_notify)"
}

# ---- UTILS ------------------------------------------------------------------
def _storage_path(date_str: str, code: str) -> Path:
    """storage パス生成 - プロジェクト統一方式"""
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"

def sha1(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _normalize_for_hash(s: str) -> str:
    """ハッシュ用正規化: NFKC→引用符統一→空白圧縮→trim"""
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

def filter_today_only(items: List[Dict], target_date: str) -> List[Dict]:
    """正規化後のitemsから、JST target_date のみを残す"""
    return [e for e in items if e.get("date") == target_date]

# ---- SCRAPING ---------------------------------------------------------------
def parse_avispa_table(soup: BeautifulSoup) -> List[Dict]:
    """アビスパ福岡J1リーグテーブルから試合情報を抽出"""
    events = []
    
    # J1リーグセクションのテーブルを特定
    j1_section = soup.find('section', id='j1league')
    if not j1_section:
        print("[DEBUG] J1 league section not found")
        return events
    
    # テーブル行を取得
    rows = j1_section.select('table tbody tr')
    print(f"[DEBUG] Found {len(rows)} table rows in J1 section")
    
    for i, row in enumerate(rows):
        cells = row.find_all('td')
        if len(cells) < 7:  # 節、日時、対戦、スタジアム、中継、結果
            continue
        
        try:
            # セル内容を取得
            section = cells[0].get_text(strip=True)
            date_time = cells[1].get_text(separator=' ', strip=True)
            opponent = cells[3].get_text(strip=True)  # 対戦相手名
            stadium_cell = cells[4]
            stadium_text = stadium_cell.get_text(strip=True)
            
            print(f"[DEBUG] Row {i+1}: {section} | {date_time} | vs {opponent} | {stadium_text}")
            
            # ベスト電器スタジアム（ベススタ）でのホームゲームのみ抽出
            if 'ベススタ' in stadium_text and 'home' in stadium_cell.get_text():
                print(f"[DEBUG] Found home game at ベススタ: {date_time} vs {opponent}")
                
                # 日時を分解
                # 例: "9/13(土) 18:00" → "9/13 18:00"
                date_time_clean = re.sub(r'\([^)]*\)', '', date_time).strip()
                
                # アビスパ福岡 vs 対戦相手のタイトル作成
                title = f"アビスパ福岡 vs {opponent}"
                
                events.append({
                    "datetime": date_time_clean,
                    "title": title,
                    "opponent": opponent,
                    "section": section,
                    "raw_stadium": stadium_text
                })
        
        except Exception as e:
            print(f"[DEBUG] Error parsing row {i+1}: {e}")
            continue
    
    print(f"[DEBUG] Extracted {len(events)} events from table")
    return events

def fetch_raw_events() -> List[Dict]:
    """アビスパ福岡公式サイトからJ1リーグ試合情報を取得"""
    try:
        print(f"[DEBUG] Fetching URL: {URL}")
        r = requests.get(URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        print(f"[DEBUG] HTTP Status: {r.status_code}")
        print(f"[DEBUG] Content length: {len(r.text)} characters")
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        # J1リーグテーブル解析
        events = parse_avispa_table(soup)
        
        # フォールバック: より広範囲なテーブル検索
        if not events:
            print("[DEBUG] Trying fallback table parsing")
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    row_text = ' '.join([cell.get_text(strip=True) for cell in cells])
                    if 'ベススタ' in row_text and re.search(r'\d{1,2}/\d{1,2}', row_text):
                        # 簡易的なデータ抽出
                        date_match = re.search(r'(\d{1,2}/\d{1,2})', row_text)
                        time_match = re.search(r'(\d{1,2}:\d{2})', row_text)
                        if date_match and time_match:
                            events.append({
                                "datetime": f"{date_match.group(1)} {time_match.group(1)}",
                                "title": "アビスパ福岡 ホームゲーム",
                                "raw_text": row_text
                            })
        
        return events
        
    except requests.RequestException as e:
        raise Exception(f"HTTP request failed: {e}")
    except Exception as e:
        raise Exception(f"Parsing failed: {e}")

# ---- MAIN -------------------------------------------------------------------
def main():
    t0 = time.time()
    
    target_date = resolve_target_date()
    include_future = os.getenv("SCRAPER_INCLUDE_FUTURE") == "1"
    
    print(f"[DEBUG] Starting best_denki_stadium scraper")
    print(f"[DEBUG] Target date: {target_date}")
    print(f"[DEBUG] Include future: {include_future}")
    
    try:
        # 1) 取得
        raw = fetch_raw_events()
        print(f"[DEBUG] Raw events: {len(raw)}")
        for event in raw:
            print(f"[DEBUG] Raw: {event}")
        
        # 2) 正規化（parser.py を使用）
        normalized: List[Dict] = []
        for e in raw:
            print(f"[DEBUG] Normalizing: {e['datetime']} | {e['title']}")
            # parser.pyのsplit_and_normalizeを使用して日付・時刻を正規化
            normalized.extend(split_and_normalize(e["datetime"], e["title"], VENUE))
        
        print(f"[DEBUG] Normalized events: {len(normalized)}")
        for norm_event in normalized:
            print(f"[DEBUG] Normalized: {norm_event}")
        
        # 3) 当日抽出（冗長化：dispatch側でも行うが、スクレイパー側でも実施）
        items = normalized if include_future else filter_today_only(normalized, target_date)
        print(f"[DEBUG] After date filtering: {len(items)} events")
        
        # 4) 重複排除＆メタ付与
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
                print(f"[DEBUG] Duplicate found, skipping: {key}")
                continue
            seen.add(h)
            
            out.append({
                "schema_version": SCHEMA_VERSION,
                **it,
                "source": URL,
                "hash": h,
                "extracted_at": extracted_at,
            })
        
        # 5) 並び替え（date, time, title）
        def _sort_key(ev: Dict):
            t = ev.get("time")
            tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
            return (ev.get("date", ""), tkey, ev.get("title", ""))
        
        out.sort(key=_sort_key)
        
        # 6) JSON保存（storage/{target_date}_g.json）
        path = _storage_path(target_date, "g")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        
        ms = int((time.time() - t0) * 1000)
        print(f"[{META['name']}] date={target_date} items={len(out)} ms={ms} url=\"{URL}\" → {path}")
        
    except Exception as e:
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\" url=\"{URL}\"")
        time.sleep(2)

if __name__ == "__main__":
    main()
