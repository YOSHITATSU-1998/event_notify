# scrapers/paypay_dome.py - 精密版
import os, json, time, re, unicodedata, sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from pathlib import Path

# パスを追加してutilsをインポート
sys.path.append(str(Path(__file__).parent.parent))
try:
    from utils.parser import JST
except ImportError:
    # JSTを直接定義
    JST = timezone(timedelta(hours=9))

# ストレージディレクトリ
STORAGE_DIR = Path(__file__).parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

# ---- META / SELECTORS -------------------------------------------------------
META = {
    "name": "paypay_dome",
    "venue": "みずほPayPayドーム",
    "url": "https://baseball.yahoo.co.jp/npb/schedule/",
    "schema_version": "1.0",
    "selector_profile": "yahoo sports precise date-based extraction",
}
URL = META["url"]
VENUE = META["venue"]
SCHEMA_VERSION = META["schema_version"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# ---- UTILS ------------------------------------------------------------------
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

def filter_today_only(items: List[Dict], target_date: str) -> List[Dict]:
    """正規化後のitemsから、JST target_date のみを残す"""
    return [e for e in items if e.get("date") == target_date]

# ---- YAHOO SPORTS PRECISE SCRAPING -----------------------------------------
def scrape_yahoo_baseball_precise() -> List[Dict]:
    """Yahoo!スポーツから今日のソフトバンク戦を日付ヘッダー基準で精密取得"""
    try:
        print(f"[paypay_dome] Accessing Yahoo Sports: {URL}")
        r = requests.get(URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        today = datetime.now(JST)
        today_str = format_japanese_date(today)  # "9月3日"
        
        print(f"[paypay_dome] Looking for date: {today_str}")
        
        events = []
        
        # 1) 今日の日付ヘッダーを探す
        date_header = find_today_date_header(soup, today_str)
        if not date_header:
            print(f"[paypay_dome] No date header found for {today_str}")
            return []
        
        print(f"[paypay_dome] Found date header: {date_header.name}.{date_header.get('class', [])}")
        
        # 2) そのヘッダーに対応する試合データを取得
        today_games = extract_games_from_date_section(date_header, today)
        
        print(f"[paypay_dome] Found {len(today_games)} games for today")
        return today_games
        
    except Exception as e:
        print(f"[paypay_dome] Yahoo baseball scraping error: {e}")
        return []

def format_japanese_date(dt: datetime) -> str:
    """datetime を日本語日付形式に変換 2025-09-03 -> 9月3日"""
    return f"{dt.month}月{dt.day}日"

def find_today_date_header(soup, today_str: str):
    """今日の日付ヘッダーを探す"""
    # th要素で探す（テーブル内のヘッダー）
    th_headers = soup.find_all('th', string=lambda text: text and today_str in text)
    if th_headers:
        print(f"[paypay_dome] Found th header: {th_headers[0].get_text(strip=True)}")
        return th_headers[0]
    
    # h2要素で探す（セクションヘッダー）
    h2_headers = soup.find_all('h2', string=lambda text: text and today_str in text)
    if h2_headers:
        print(f"[paypay_dome] Found h2 header: {h2_headers[0].get_text(strip=True)}")
        return h2_headers[0]
    
    return None

def extract_games_from_date_section(date_header, today: datetime) -> List[Dict]:
    """日付ヘッダーから対応する試合データを抽出"""
    games = []
    
    if date_header.name == 'th':
        # th要素の場合：同じテーブル内で、そのthの後の行を取得
        games = extract_games_from_table_header(date_header, today)
    elif date_header.name == 'h2':
        # h2要素の場合：次のセクション内のテーブルを取得
        games = extract_games_from_section_header(date_header, today)
    
    return games

def extract_games_from_table_header(th_header, today: datetime) -> List[Dict]:
    """thヘッダー後の同一テーブル内の試合を抽出"""
    games = []
    
    # thの親のtr要素を取得
    tr = th_header.find_parent('tr')
    if not tr:
        return games
    
    # そのtr要素の後続のtr要素を取得
    next_trs = []
    current = tr.find_next_sibling('tr')
    
    while current:
        text = current.get_text(' ', strip=True)
        
        # 新しい日付ヘッダーが出現したら停止
        if re.search(r'\d+月\d+日', text) and '（' in text:
            break
            
        # ソフトバンク戦があれば処理
        if 'ソフトバンク' in text and 'みずほPayPay' in text:
            game = parse_precise_game(current, today)
            if game:
                print(f"[paypay_dome] Table game extracted: {game['title']} at {game.get('time', 'TBA')}")
                games.append(game)
        
        current = current.find_next_sibling('tr')
        
        # 安全弁：最大10行まで
        if len(next_trs) > 10:
            break
            
        next_trs.append(current)
    
    return games

def extract_games_from_section_header(h2_header, today: datetime) -> List[Dict]:
    """h2ヘッダー後のセクション内の試合を抽出"""
    games = []
    
    # h2の次の要素から順次探索
    current = h2_header.find_next_sibling()
    
    while current:
        # 新しいh2が出現したら停止
        if current.name == 'h2':
            break
            
        # テーブルがあれば中身をチェック
        if current.name == 'table':
            rows = current.select('tr')
            for row in rows:
                text = row.get_text(' ', strip=True)
                if 'ソフトバンク' in text and 'みずほPayPay' in text:
                    game = parse_precise_game(row, today)
                    if game:
                        print(f"[paypay_dome] Section game extracted: {game['title']} at {game.get('time', 'TBA')}")
                        games.append(game)
        
        current = current.find_next_sibling()
        
        # 安全弁
        if not current:
            break
    
    return games

def parse_precise_game(row, today: datetime) -> Dict:
    """行から試合情報を精密解析（試合結果も含む）"""
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
    if '試合終了' in main_content:
        game_status = "試合終了"
        print(f"[paypay_dome] Found finished game: {main_content[:50]}")
    elif '試合前' in main_content:
        print(f"[paypay_dome] Found upcoming game: {main_content[:50]}")
    
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
        print(f"[paypay_dome] No opponent found in: {main_content}")
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
        "date": today.strftime("%Y-%m-%d"),
        "time": game_time,
        "title": title,
        "venue": VENUE,
        "game_status": game_status,  # 試合前 or 試合終了
        "score": score_info,  # 試合終了の場合のみ
        "raw_data": main_content,
        "for_notification": game_status == "試合前"  # 通知対象フラグ
    }

# ---- MAIN SCRAPING LOGIC ---------------------------------------------------
def fetch_raw_events() -> List[Dict]:
    """精密な野球試合取得"""
    all_events = []
    
    # Yahoo!スポーツから精密に野球試合を取得
    print("[paypay_dome] Fetching baseball games with precise date filtering...")
    baseball_events = scrape_yahoo_baseball_precise()
    all_events.extend(baseball_events)
    print(f"[paypay_dome] Precise baseball games: {len(baseball_events)}")
    
    return all_events

# ---- MAIN -------------------------------------------------------------------
def main():
    t0 = time.time()
    
    target_date = resolve_target_date()
    include_future = os.getenv("SCRAPER_INCLUDE_FUTURE") == "1"
    
    try:
        print(f"[{META['name']}] target_date={target_date}")
        
        # 1) 精密取得
        raw = fetch_raw_events()
        
        # 2) 当日抽出（冗長化）
        items = raw if include_future else filter_today_only(raw, target_date)
        
        # 3) データ検証：同じ時刻に複数の対戦相手がいる場合は警告
        validate_game_data(items)
        
        # 4) 重複排除＆メタ付与
        seen = set()
        out: List[Dict] = []
        extracted_at = datetime.now(JST).isoformat()
        
        for it in items:
            title_norm = _normalize_for_hash(it.get("title", ""))
            venue_norm = _normalize_for_hash(it.get("venue", ""))
            date_part = it.get("date", "")
            time_part = it.get("time") or ""  # None→空
            
            key = f"{date_part}|{time_part}|{title_norm}|{venue_norm}"
            h = sha1(key)
            if h in seen:
                continue
            seen.add(h)
            
            # raw_dataは出力JSONから除外
            clean_item = {k: v for k, v in it.items() if k != "raw_data"}
            
            out.append({
                "schema_version": SCHEMA_VERSION,
                **clean_item,  # date / time / title / venue
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
        
        # 6) JSON保存
        path = STORAGE_DIR / f"{target_date}_f.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        
        ms = int((time.time() - t0) * 1000)
        print(f"[{META['name']}] date={target_date} items={len(out)} ms={ms} method=yahoo_precise url=\"{URL}\" → {path}")
        
    except requests.RequestException as e:
        print(f"[{META['name']}][ERROR] Network error: {e}")
    except Exception as e:
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\" url=\"{URL}\"")

def validate_game_data(items: List[Dict]):
    """データ検証：不正な重複をチェック"""
    if len(items) == 0:
        print("[paypay_dome] WARNING: No games found for today")
        return
    
    # 同じ時刻に複数の対戦相手がいる場合は警告
    time_opponents = {}
    for item in items:
        time_key = item.get("time", "無時刻")
        if time_key not in time_opponents:
            time_opponents[time_key] = []
        time_opponents[time_key].append(item.get("title", ""))
    
    for time_key, titles in time_opponents.items():
        if len(titles) > 1:
            print(f"[paypay_dome] WARNING: Multiple opponents at {time_key}: {titles}")
        else:
            print(f"[paypay_dome] OK: {time_key} - {titles[0]}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"[{META['name']}] Interrupted by user")
    except Exception as e:
        print(f"[{META['name']}][ERROR] Unexpected error: {e}")
        time.sleep(1)
