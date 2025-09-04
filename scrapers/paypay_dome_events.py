# scrapers/paypay_dome_events.py
import os, json, time, re, unicodedata
from datetime import datetime
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from event_notify.utils.parser import JST
from event_notify.utils.paths import STORAGE_DIR

# ---- META / SELECTORS -------------------------------------------------------
META = {
    "name": "paypay_dome_events",
    "venue": "みずほPayPayドーム",
    "url": "https://www.softbankhawks.co.jp/stadium/event_schedule/2025/",
    "schema_version": "1.0",
    "selector_profile": "static HTML with month sections; date + event pattern",
}
URL = META["url"]
VENUE = META["venue"]
SCHEMA_VERSION = META["schema_version"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EventBot/1.0; +https://example.com/contact)"
}

# ---- UTILS ------------------------------------------------------------------
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

def filter_today_only(items: List[Dict], target_date: str) -> List[Dict]:
    """正規化後のitemsから、JST target_date のみを残す"""
    return [e for e in items if e.get("date") == target_date]

def parse_paypay_date(date_str: str) -> str:
    """
    "2025/9/5（木）" → "2025-09-05"
    """
    # 基本パターン: 2025/9/5
    match = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})', date_str.strip())
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return None

def extract_event_time(time_str: str) -> str:
    """
    "開場 16:00 開演 18:00" → "18:00"
    開演時刻を優先、なければ開場時刻
    """
    # 開演時刻を優先抽出
    start_match = re.search(r'開演\s*(\d{1,2}:\d{2})', time_str)
    if start_match:
        return start_match.group(1)
    
    # 開場時刻をフォールバック
    open_match = re.search(r'開場\s*(\d{1,2}:\d{2})', time_str)
    if open_match:
        return open_match.group(1)
    
    return None  # 時刻未定

def extract_event_title(title_str: str) -> str:
    """
    "[第39回 Golden Disc Awards](https://www.osipass.jp/)" → "第39回 Golden Disc Awards"
    """
    # [タイトル](URL) パターンから抽出
    match = re.search(r'\[([^\]]+)\]', title_str)
    if match:
        return match.group(1).strip()
    
    # マークダウンリンクでない場合はそのまま返す
    return title_str.strip()

# ---- SCRAPING ---------------------------------------------------------------
def fetch_raw_events() -> List[Dict]:
    """PayPayドーム公式サイトからイベント情報を取得"""
    r = requests.get(URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    events = []
    current_date = None
    
    # HTMLテキストを行ごとに処理
    text_content = soup.get_text()
    lines = [line.strip() for line in text_content.split('\n') if line.strip()]
    
    for i, line in enumerate(lines):
        # 日付行を検出: "2025/9/5（木）"
        if re.match(r'\d{4}/\d{1,2}/\d{1,2}（.+）', line):
            current_date = line
            continue
        
        # イベント行を検出: "イベント [タイトル](URL)"
        if line.startswith('イベント ') and current_date:
            event_title = line.replace('イベント ', '', 1)
            
            # 次の行から時刻情報を取得
            time_info = ""
            for j in range(i + 1, min(i + 5, len(lines))):  # 次の数行を確認
                next_line = lines[j]
                if re.search(r'開[場演]', next_line):
                    time_info += " " + next_line
                elif next_line.startswith('お問い合わせ'):
                    break
                elif re.match(r'\d{4}/\d{1,2}/\d{1,2}（.+）', next_line):
                    break  # 次の日付が始まった
            
            events.append({
                "date_raw": current_date,
                "title_raw": event_title,
                "time_raw": time_info.strip()
            })
    
    return events

def normalize_events(raw_events: List[Dict]) -> List[Dict]:
    """生データを正規化してevent_notify形式に変換"""
    normalized = []
    
    for raw in raw_events:
        # 日付正規化
        date = parse_paypay_date(raw["date_raw"])
        if not date:
            continue
        
        # 時刻抽出
        time = extract_event_time(raw["time_raw"])
        
        # タイトル抽出
        title = extract_event_title(raw["title_raw"])
        
        normalized.append({
            "date": date,
            "time": time,
            "title": title,
            "venue": VENUE,
            "event_type": "event"  # 野球と区別
        })
    
    return normalized

# ---- MAIN -------------------------------------------------------------------
def main():
    t0 = time.time()

    target_date = resolve_target_date()
    include_future = os.getenv("SCRAPER_INCLUDE_FUTURE") == "1"

    # 1) 取得
    raw = fetch_raw_events()

    # 2) 正規化
    normalized = normalize_events(raw)

    # 3) 当日抽出
    items = normalized if include_future else filter_today_only(normalized, target_date)

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
            continue
        seen.add(h)

        out.append({
            "schema_version": SCHEMA_VERSION,
            **it,
            "source": URL,
            "hash": h,
            "extracted_at": extracted_at,
        })

    # 5) 並び替え
    def _sort_key(ev: Dict):
        t = ev.get("time")
        tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
        return (ev.get("date", ""), tkey, ev.get("title", ""))

    out.sort(key=_sort_key)

    # 6) JSON保存（storage/{target_date}_f_event.json）
    path = STORAGE_DIR / f"{target_date}_f_event.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    ms = int((time.time() - t0) * 1000)
    print(f"[{META['name']}] date={target_date} items={len(out)} ms={ms} url=\"{URL}\" → {path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\" url=\"{URL}\"")
        time.sleep(1)
