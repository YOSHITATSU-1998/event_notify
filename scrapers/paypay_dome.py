#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PayPayドーム（野球）スクレイパー Ver.2.0
対応期間: 8週分（約2ヶ月分）の野球試合情報取得
データソース: Yahoo!スポーツ NPBスケジュール（週別URL）
"""

import os
import json
import time
import re
import unicodedata
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from event_notify.utils.parser import JST

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
    "name": "paypay_dome",
    "venue": "みずほPayPayドーム",
    "url_base": "https://baseball.yahoo.co.jp/npb/schedule/",
    "schema_version": "1.0",
    "selector_profile": "yahoo sports weekly date-based extraction; multi-week support",
}

BASE_URL = META["url_base"]
VENUE = META["venue"]
SCHEMA_VERSION = META["schema_version"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# ---- UTILS ------------------------------------------------------------------
def _storage_path(date_str: str, code: str) -> Path:
    """Ver.2.0統一ストレージパス"""
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"

def sha1(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _normalize_for_hash(s: str) -> str:
    """ハッシュ用の軽量正規化"""
    if s is None:
        return ""
    x = unicodedata.normalize("NFKC", s)
    x = x.replace(""", '"').replace(""", '"').replace("‟", '"').replace("〝", '"').replace("〞", '"')
    x = x.replace("'", "'").replace("'", "'").replace("＇", "'")
    x = re.sub(r"\s+", " ", x).strip()
    return x

def resolve_target_date() -> str:
    """環境変数でターゲット日付を上書き可能。未指定ならJST今日"""
    override = os.getenv("SCRAPER_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")

def get_target_date_range() -> tuple[str, str]:
    """当月1日～翌月末日の期間を取得（Ver.2.0用）"""
    today = datetime.now(JST)
    
    # 当月1日
    start_date = today.replace(day=1)
    
    # 翌月末日計算
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
        end_date = next_month.replace(month=2, day=1) - timedelta(days=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
        if next_month.month == 12:
            end_date = next_month.replace(year=next_month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = next_month.replace(month=next_month.month + 1, day=1) - timedelta(days=1)
    
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
                "notes": f"game_status: {event.get('game_status', '')}, score: {event.get('score', '')}"
            }
            db_records.append(record)
        
        # バッチ挿入（重複は無視）
        result = supabase.table('events').upsert(
            db_records,
            on_conflict="data_hash"
        ).execute()
        
        print(f"[{META['name']}] DB投入成功: {len(result.data)}件")
        
    except Exception as e:
        print(f"[{META['name']}][ERROR] DB投入失敗: {e}")

# ---- WEEKLY BASEBALL SCRAPING -----------------------------------------------
def get_monday_of_week(target_date: datetime) -> datetime:
    """指定日を含む週の月曜日を取得"""
    weekday = target_date.weekday()  # 0=月, 1=火, ... 6=日
    monday = target_date - timedelta(days=weekday)
    return monday

def fetch_multi_week_baseball(weeks_ahead: int = 8) -> List[Dict]:
    """8週分（約2ヶ月）の野球試合取得"""
    all_games = []
    base_date = datetime.now(JST)
    
    print(f"[{META['name']}] Fetching {weeks_ahead + 1} weeks of baseball games...")
    
    # 今週の月曜日を起点として計算
    base_monday = get_monday_of_week(base_date)
    
    for week in range(weeks_ahead + 1):
        target_monday = base_monday + timedelta(weeks=week)
        url = f"{BASE_URL}?date={target_monday.strftime('%Y-%m-%d')}"
        
        try:
            print(f"[{META['name']}] Week {week}: {target_monday.strftime('%Y-%m-%d')} (Monday) -> {url}")
            week_games = scrape_week_games(url, target_monday)
            all_games.extend(week_games)
            
            # アクセス間隔（礼儀として）
            if week < weeks_ahead:
                time.sleep(1)
                
        except Exception as e:
            print(f"[{META['name']}] Failed week {week} ({target_monday.strftime('%Y-%m-%d')}): {e}")
            continue
    
    return all_games

def scrape_week_games(url: str, monday_date: datetime) -> List[Dict]:
    """指定URLから1週間分の試合データを取得"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        games = []
        
        # その週の全ての日付を生成（月曜～日曜）
        week_dates = []
        for i in range(7):
            date = monday_date + timedelta(days=i)
            week_dates.append({
                "date": date,
                "japanese": format_japanese_date(date),
                "iso": date.strftime("%Y-%m-%d")
            })
        
        # 各日付について試合を検索
        for date_info in week_dates:
            daily_games = find_games_for_date(soup, date_info)
            games.extend(daily_games)
        
        print(f"[{META['name']}] Week {monday_date.strftime('%Y-%m-%d')}: found {len(games)} Hawks games")
        return games
        
    except Exception as e:
        print(f"[{META['name']}] Error scraping {url}: {e}")
        return []

def format_japanese_date(dt: datetime) -> str:
    """datetime を日本語日付形式に変換 2025-09-18 -> 9月18日"""
    return f"{dt.month}月{dt.day}日"

def find_games_for_date(soup: BeautifulSoup, date_info: dict) -> List[Dict]:
    """指定日付のソフトバンク戦を検索"""
    games = []
    japanese_date = date_info["japanese"]
    iso_date = date_info["iso"]
    
    # 日付ヘッダーを探す（thまたはh2）
    date_header = find_date_header(soup, japanese_date)
    if not date_header:
        return games
    
    # 日付ヘッダーから対応する試合データを抽出
    if date_header.name == 'th':
        games = extract_games_from_table_header(date_header, iso_date)
    elif date_header.name in ['h2', 'h3']:
        games = extract_games_from_section_header(date_header, iso_date)
    
    return games

def find_date_header(soup: BeautifulSoup, japanese_date: str):
    """指定日付のヘッダーを探す"""
    # th要素で探す（テーブル内のヘッダー）
    th_headers = soup.find_all('th', string=lambda text: text and japanese_date in text)
    if th_headers:
        return th_headers[0]
    
    # h2要素で探す（セクションヘッダー）
    h2_headers = soup.find_all('h2', string=lambda text: text and japanese_date in text)
    if h2_headers:
        return h2_headers[0]
    
    # h3要素で探す（サブセクションヘッダー）
    h3_headers = soup.find_all('h3', string=lambda text: text and japanese_date in text)
    if h3_headers:
        return h3_headers[0]
    
    return None

def extract_games_from_table_header(th_header, iso_date: str) -> List[Dict]:
    """thヘッダー後の同一テーブル内の試合を抽出"""
    games = []
    
    # thの親のtr要素を取得
    tr = th_header.find_parent('tr')
    if not tr:
        return games
    
    # そのtr要素の後続のtr要素を取得
    current = tr.find_next_sibling('tr')
    
    safety_counter = 0
    while current and safety_counter < 20:
        text = current.get_text(' ', strip=True)
        
        # 新しい日付ヘッダーが出現したら停止
        if re.search(r'\d+月\d+日', text) and '（' in text:
            break
        
        # ソフトバンク戦があれば処理
        if 'ソフトバンク' in text and 'みずほPayPay' in text:
            game = parse_game_row(current, iso_date)
            if game:
                games.append(game)
        
        current = current.find_next_sibling('tr')
        safety_counter += 1
    
    return games

def extract_games_from_section_header(header, iso_date: str) -> List[Dict]:
    """h2/h3ヘッダー後のセクション内の試合を抽出"""
    games = []
    
    # ヘッダーの次の要素から順次探索
    current = header.find_next_sibling()
    
    safety_counter = 0
    while current and safety_counter < 50:
        # 新しいヘッダーが出現したら停止
        if current.name in ['h1', 'h2', 'h3']:
            break
        
        # テーブルがあれば中身をチェック
        if current.name == 'table':
            rows = current.select('tr')
            for row in rows:
                text = row.get_text(' ', strip=True)
                if 'ソフトバンク' in text and 'みずほPayPay' in text:
                    game = parse_game_row(row, iso_date)
                    if game:
                        games.append(game)
        
        current = current.find_next_sibling()
        safety_counter += 1
    
    return games

def parse_game_row(row, iso_date: str) -> Dict:
    """行から試合情報を解析（Ver.2.0版：試合結果も含む）"""
    cells = row.select('td, th')
    if len(cells) < 2:
        return None
    
    main_content = cells[0].get_text(' ', strip=True)
    venue_content = cells[1].get_text(' ', strip=True)
    
    # venue確認（みずほPayPayドームでなければ除外）
    if 'みずほPayPay' not in venue_content:
        return None
    
    # 試合状況を判定
    game_status = "試合前"
    for_notification = True  # デフォルトは通知対象
    
    if '試合終了' in main_content:
        game_status = "試合終了"
        for_notification = False  # 試合終了は通知対象外
    elif '試合前' in main_content or '開始前' in main_content:
        game_status = "試合前"
        for_notification = True
    
    # 時刻を抽出
    time_match = re.search(r'(\d{1,2}:\d{2})', main_content)
    game_time = None
    if time_match:
        time_str = time_match.group(1)
        hour, minute = time_str.split(':')
        game_time = f"{int(hour):02d}:{int(minute):02d}"
    
    # 対戦相手を特定
    opponents = ['オリックス', 'ロッテ', '楽天', '日本ハム', '西武', '巨人', '阪神', 'ヤクルト', '広島', 'DeNA', '中日']
    opponent = None
    for team in opponents:
        if team in main_content:
            opponent = team
            break
    
    if not opponent:
        return None
    
    title = f"福岡ソフトバンクホークス vs {opponent}"
    
    # 試合結果の場合はスコアを抽出
    score_info = None
    if game_status == "試合終了":
        score_match = re.search(r'(\d+)\s*-\s*(\d+)', main_content)
        if score_match:
            hawks_score, opponent_score = score_match.groups()
            score_info = f"{hawks_score}-{opponent_score}"
    
    return {
        "date": iso_date,
        "time": game_time,
        "title": title,
        "venue": VENUE,
        "game_status": game_status,
        "score": score_info,
        "for_notification": for_notification
    }

# ---- MAIN -------------------------------------------------------------------
def main():
    t0 = time.time()
    
    target_date = resolve_target_date()
    
    try:
        print(f"[{META['name']}] target_date={target_date}")
        
        # 1) 8週分の野球試合取得（全期間データ）
        all_games = fetch_multi_week_baseball()
        
        # 2) 期間範囲計算（当月1日～翌月末日）
        start_date, end_date = get_target_date_range()
        print(f"[{META['name']}] Target range: {start_date} ~ {end_date}")
        
        # 3) 期間フィルタリング（Ver.2.0用）
        filtered_games = filter_date_range(all_games, start_date, end_date)
        
        # 4) 重複排除＆メタ付与
        seen = set()
        out: List[Dict] = []
        extracted_at = datetime.now(JST).isoformat()
        
        for it in filtered_games:
            title_norm = _normalize_for_hash(it.get("title", ""))
            venue_norm = _normalize_for_hash(it.get("venue", ""))
            date_part = it.get("date", "")
            time_part = it.get("time") or ""
            
            key = f"{date_part}|{title_norm}|{venue_norm}"
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
        
        # 5) 並び替え（date, time, title）
        def _sort_key(ev: Dict):
            t = ev.get("time")
            tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
            return (ev.get("date", ""), tkey, ev.get("title", ""))
        
        out.sort(key=_sort_key)
        
        # 6) JSON保存（storage/{target_date}_f.json）— Ver.2.0: 全期間データを保存
        path = _storage_path(target_date, "f")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        
        # 7) Supabase投入（Ver.2.0用・新機能）
        db_enabled = os.getenv("ENABLE_DB_SAVE", "0") == "1"
        if db_enabled and SUPABASE_AVAILABLE:
            save_to_supabase(out)
        elif db_enabled:
            print(f"[{META['name']}] DB投入スキップ: Supabase依存関係不足")
        
        ms = int((time.time() - t0) * 1000)
        print(f"[{META['name']}] date={target_date} items={len(out)} range={start_date}~{end_date} weeks=9 ms={ms} → {path}")
        
    except requests.RequestException as e:
        print(f"[{META['name']}][ERROR] Network error: {e}")
    except Exception as e:
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\" url=\"{BASE_URL}\"")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"[{META['name']}] Interrupted by user")
    except Exception as e:
        print(f"[{META['name']}][ERROR] Unexpected error: {e}")
        time.sleep(1)
