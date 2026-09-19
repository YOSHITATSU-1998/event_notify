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

def fetch_raw_events() -> List[Dict]:
    """アビスパ福岡公式サイトから全試合情報を取得（新カード構造 div.fixture-row 対応版）"""
    try:
        print(f"[DEBUG] Fetching URL: {URL}")
        r = requests.get(URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        print(f"[DEBUG] HTTP Status: {r.status_code}")
        print(f"[DEBUG] Content length: {len(r.text)} characters")

        soup = BeautifulSoup(r.text, "html.parser")
        events = []

        # 新UI: <div class="fixture-row"> からベスト電器スタジアムのHOMEゲームを抽出
        fixture_rows = soup.select("div.fixture-row")
        print(f"[DEBUG] Found {len(fixture_rows)} fixture-rows")

        for i, row in enumerate(fixture_rows):
            stadium_elem = row.select_one("span.fixture-stadium")
            stadium_text = stadium_elem.get_text(strip=True) if stadium_elem else ""

            # スタジアム名判定: 「ベスト電器」「ベススタ」「べススタ」
            if not ("ベスト電器" in stadium_text or "ベススタ" in stadium_text or "べススタ" in stadium_text):
                continue

            badge_elem = row.select_one("span.fixture-badge")
            badge_text = badge_elem.get_text(strip=True) if badge_elem else ""

            # HOMEゲームのみ抽出
            if "HOME" not in badge_text.upper():
                continue

            # 大会名
            tour_elem = row.select_one("div.fixture-tournament")
            tour_sp = tour_elem.select_one("span.pc") if tour_elem else None
            tour_text = tour_sp.get_text(strip=True) if tour_sp else (tour_elem.get_text(strip=True) if tour_elem else "")

            # 日付
            date_elem = row.select_one("span.fixture-num")
            date_str = date_elem.get_text(strip=True) if date_elem else ""

            # キックオフ時間
            time_elem = row.select_one("span.fixture-num-time")
            time_str = time_elem.get_text(strip=True) if time_elem else ""

            # 対戦相手
            opp_elem = row.select_one("span.fixture-opponent-name")
            opp_text = opp_elem.get_text(strip=True) if opp_elem else ""

            if not date_str:
                continue

            # タイトル構築
            title = f"アビスパ福岡 vs {opp_text}" if opp_text else "アビスパ福岡 ホームゲーム"

            # 日時文字列（parser.py が受け取れる形式: "8/8 19:00"）
            datetime_clean = f"{date_str} {time_str}".strip()

            print(f"[DEBUG] Hit: {tour_text} | {datetime_clean} | vs {opp_text} | {stadium_text}")

            events.append({
                "datetime": datetime_clean,
                "title": title,
                "opponent": opp_text,
                "section": tour_text,
                "raw_stadium": stadium_text,
            })

        # フォールバック: fixture-row で0件だった場合、旧テーブル構造も念のため検索
        if not events:
            print("[DEBUG] Trying fallback table parsing")
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    row_text = ' '.join([cell.get_text(strip=True) for cell in cells])
                    if ('ベススタ' in row_text or 'べススタ' in row_text or 'ベスト電器' in row_text) and \
                            re.search(r'\d{1,2}/\d{1,2}', row_text) and 'home' in row_text.lower():
                        date_match = re.search(r'(\d{1,2}/\d{1,2})', row_text)
                        time_match = re.search(r'(\d{1,2}:\d{2})', row_text)
                        if date_match:
                            dt = f"{date_match.group(1)} {time_match.group(1)}" if time_match else date_match.group(1)
                            events.append({
                                "datetime": dt,
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
