# scrapers/marinemesse_a.py
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
    "name": "marinemesse_a",
    "venue": "マリンメッセA館",
    "url": "https://www.marinemesse.or.jp/messe/event/",
    "schema_version": "1.0",
    "selector_profile": "table > tr with 2+ tds; alt: .event-list .event",
}
URL = META["url"]
VENUE = META["venue"]
SCHEMA_VERSION = META["schema_version"]

SELECTORS = {
    # 1st: 安定（現行のテーブル行想定）
    "primary": "table tr",
    # 2nd: フォールバック（将来 .event-list などに変わった場合）
    "fallback": ".event-list .event, .events .event, .eventItem",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EventBot/1.0; +https://example.com/contact)"
}

# ---- UTILS ------------------------------------------------------------------
def _storage_path(date_str: str, code: str) -> Path:
    """congress_b.py と同じ方式で storage パス生成"""
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
      - 引用符ゆれを統一（" " ‟ 〝 〞 → "、 ' ' ＇ → '）
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

# ---- SCRAPING ---------------------------------------------------------------
def fetch_raw_events() -> List[Dict]:
    """DOM変更に強い最小取得：primary→fallback の2系統"""
    r = requests.get(URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    events = []

    # Primary: table rows
    rows = soup.select(SELECTORS["primary"])
    if rows:
        for tr in rows:
            tds = [td.get_text(" ", strip=True) for td in tr.select("td")]
            if len(tds) >= 2:
                events.append({"datetime": tds[0], "title": tds[1]})

    # Fallback: common event-card patterns
    if not events:
        for ev in soup.select(SELECTORS["fallback"]):
            # 汎用的に日付/時刻 + タイトル らしきテキストを抽出（保険）
            text = ev.get_text(" ", strip=True)
            # 例: "8/30(金) 10:30 〜 ディズニー・オン・アイス"
            # 最低限、「タイトルらしき末尾」と「先頭の日時ブロック」を分解
            parts = re.split(r"\s{2,}| {1,}—| {1,}–| {1,}-", text)
            if len(parts) >= 2:
                events.append({"datetime": parts[0], "title": parts[-1]})

    return events

# ---- MAIN -------------------------------------------------------------------
def main():
    t0 = time.time()

    target_date = resolve_target_date()
    include_future = os.getenv("SCRAPER_INCLUDE_FUTURE") == "1"

    # 1) 取得
    raw = fetch_raw_events()

    # 2) 正規化（「8.29(金) 10:30～ …」→ date/time/title/venue の配列に展開）
    normalized: List[Dict] = []
    for e in raw:
        normalized.extend(split_and_normalize(e["datetime"], e["title"], VENUE))

    # 3) 当日抽出（冗長化：スクレイパ側でも today を絞る。フラグで全量にも切替可）
    items = normalized if include_future else filter_today_only(normalized, target_date)

    # 4) 重複排除＆メタ付与（ハッシュ：date|time|title|venue）
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

        out.append({
            "schema_version": SCHEMA_VERSION,
            **it,  # date / time / title / venue
            "source": URL,
            "hash": h,
            "extracted_at": extracted_at,
        })

    # 5) 並び替え（date, time(欠損は"99:99"で末尾), title）
    def _sort_key(ev: Dict):
        t = ev.get("time")
        tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
        return (ev.get("date", ""), tkey, ev.get("title", ""))

    out.sort(key=_sort_key)

    # 6) JSON保存（storage/{target_date}_a.json）— プロジェクト統一方針に合わせて空配列も保存
    path = _storage_path(target_date, "a")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    ms = int((time.time() - t0) * 1000)
    print(f"[{META['name']}] date={target_date} items={len(out)} ms={ms} url=\"{URL}\" → {path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 失敗時はファイル非生成（推奨）。ログのみを1行で残す。
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\" url=\"{URL}\"")
        time.sleep(1)  # 他ステップへの影響を減らすための軽い間（任意）
