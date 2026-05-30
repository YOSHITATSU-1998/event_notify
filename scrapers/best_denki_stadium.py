# scrapers/best_denki_stadium.py Ver.2.0 + DB投入機能
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

# スクレイピング対象セクションIDとその大会名
TARGET_SECTIONS = [
    ("j1league",    "J1リーグ"),
    ("levaincup",   "ルヴァンカップ"),
    ("emperorscup", "プレーオフ/天皇杯"),
]

def parse_section_table(section_elem, section_name: str) -> List[Dict]:
    """
    指定セクション要素内のテーブルからベススタ・ホームゲームを抽出する汎用パーサー。
    列数が 5〜7 列のテーブルに対応（J1:7列、プレーオフ:7列 など）。
    """
    events = []
    rows = section_elem.select('table tbody tr')
    print(f"[DEBUG] [{section_name}] Found {len(rows)} rows")

    for i, row in enumerate(rows):
        cells = row.find_all('td')
        # 最低 5 列必要（丸ごとコラムスパンがある場合も考慮）
        if len(cells) < 5:
            continue

        try:
            # --- 列レイアウトを動的に検出 ---
            # スタジアム列: "ベススタ" or "べススタ" を含む td を検索
            stadium_cell = None
            stadium_idx = -1
            for idx, cell in enumerate(cells):
                txt = cell.get_text(strip=True)
                if 'ベススタ' in txt or 'べススタ' in txt:
                    stadium_cell = cell
                    stadium_idx = idx
                    break

            if stadium_cell is None:
                continue  # このセクションでベススタ以外の会場はスキップ

            # home/away 判定
            if 'home' not in stadium_cell.get_text():
                continue  # アウェイはスキップ

            # --- 日時列を取得（stadium の手前から探す） ---
            # 日時セルは「月/日(曜日)」パターンを含む td
            date_time_text = None
            for cell in cells[:stadium_idx]:
                txt = cell.get_text(separator=' ', strip=True)
                if re.search(r'\d{1,2}/\d{1,2}', txt):
                    date_time_text = txt
                    break

            if not date_time_text:
                print(f"[DEBUG] [{section_name}] Row {i+1}: date not found, skip")
                continue

            # --- 対戦相手列 ---
            # 対戦相手: スタジアム列の手前 1〜2 列に入っていることが多い
            opponent = ""
            for cell in reversed(cells[:stadium_idx]):
                txt = cell.get_text(strip=True)
                # エンブレム span のテキストや「FC」「ヴィッセル」等を含む
                if txt and not re.fullmatch(r'\d+|\d+\.\d+', txt):
                    # 「節番号」「戦番号」ではないか確認
                    if not re.fullmatch(r'\d+(回戦|節|戦)?', txt):
                        opponent = txt
                        break

            # --- タイトル ---
            # 節番号
            round_label = cells[0].get_text(strip=True)
            title = f"アビスパ福岡 vs {opponent}" if opponent else f"アビスパ福岡 ホームゲーム ({section_name})"

            # 日時クリーニング: 曜日括弧除去
            date_time_clean = re.sub(r'\([^)]*\)', '', date_time_text).strip()

            stadium_text = stadium_cell.get_text(strip=True)
            print(f"[DEBUG] [{section_name}] Hit: {round_label} | {date_time_clean} | vs {opponent} | {stadium_text}")

            events.append({
                "datetime": date_time_clean,
                "title": title,
                "opponent": opponent,
                "section": f"{section_name}:{round_label}",
                "raw_stadium": stadium_text,
            })

        except Exception as e:
            print(f"[DEBUG] [{section_name}] Error row {i+1}: {e}")
            continue

    return events


def parse_avispa_all_sections(soup: BeautifulSoup) -> List[Dict]:
    """
    全大会セクション（J1・ルヴァン・プレーオフ/天皇杯）からベススタ・ホームゲームを収集する。
    """
    all_events: List[Dict] = []

    for section_id, section_name in TARGET_SECTIONS:
        section_elem = soup.find('section', id=section_id)
        if not section_elem:
            print(f"[DEBUG] Section '{section_id}' not found, skipping")
            continue
        found = parse_section_table(section_elem, section_name)
        all_events.extend(found)

    # emperorscup id は複数存在する場合があるため、find_all でも念のため補足
    seen_ids = {s_id for s_id, _ in TARGET_SECTIONS}
    for section_elem in soup.find_all('section'):
        sid = section_elem.get('id', '')
        if sid and sid not in seen_ids:
            # 新規セクションは念のため全取得（プレーオフラウンドなど id 変更があっても対応）
            found = parse_section_table(section_elem, sid)
            if found:
                print(f"[DEBUG] Extra section '{sid}': found {len(found)} home games")
                all_events.extend(found)
            seen_ids.add(sid)

    print(f"[DEBUG] Total home games across all sections: {len(all_events)}")
    return all_events


def fetch_raw_events() -> List[Dict]:
    """アビスパ福岡公式サイトから全大会の試合情報を取得（全セクション対応版）"""
    try:
        print(f"[DEBUG] Fetching URL: {URL}")
        r = requests.get(URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        print(f"[DEBUG] HTTP Status: {r.status_code}")
        print(f"[DEBUG] Content length: {len(r.text)} characters")

        soup = BeautifulSoup(r.text, "html.parser")

        # 全セクション解析（J1・ルヴァン・プレーオフ/天皇杯）
        events = parse_avispa_all_sections(soup)

        # フォールバック: 全セクションで0件だった場合のみ広範囲検索
        if not events:
            print("[DEBUG] Trying fallback table parsing")
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    row_text = ' '.join([cell.get_text(strip=True) for cell in cells])
                    if ('ベススタ' in row_text or 'べススタ' in row_text) and \
                            re.search(r'\d{1,2}/\d{1,2}', row_text) and 'home' in row_text:
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
    
    print(f"[DEBUG] Starting best_denki_stadium scraper")
    print(f"[DEBUG] Target date: {target_date}")
    
    try:
        # 1) 全期間データ取得
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
        
        # 期間範囲計算（当月1日～翌月末日）
        start_date, end_date = get_target_date_range()
        print(f"[{META['name']}] Target range: {start_date} ~ {end_date}")

        # 3) 期間フィルタリング（当月1日～翌月末日）
        all_events = filter_date_range(normalized, start_date, end_date)
        print(f"[DEBUG] After date filtering: {len(all_events)} events")
        
        # 4) 重複排除＆メタ付与（全期間データ - Ver.2.0用）
        seen = set()
        out: List[Dict] = []
        extracted_at = datetime.now(JST).isoformat()
        
        for it in all_events:
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
        
        # 6) JSON保存（storage/{target_date}_g.json）— Ver.2.0: 全期間データを保存
        path = _storage_path(target_date, "g")
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
        
    except Exception as e:
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\" url=\"{URL}\"")
        time.sleep(2)

if __name__ == "__main__":
    main()
