# scrapers/congress_b.py
# 福岡国際会議場（思い出ネーム: コングレスB）
# 出力：storage/{date}_d.json（schema_version=1.0）
# 既定は「JSTの今日」だけを書き出す。検証用に環境変数で切替可。
# 実行: PS> python -m scrapers.congress_b

from __future__ import annotations
import os
import re
import json
import time
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup

# 🔥 parser.py をインポート
try:
    from utils.parser import split_and_normalize
except ImportError:
    # モジュールパス問題の場合のフォールバック
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from utils.parser import split_and_normalize

# ========= META =========
META = {
    "name": "congress_b",
    "venue": "福岡国際会議場",
    "code": "d",
    "url_candidates": [
        "https://www.marinemesse.or.jp/congress/event/",
        #"https://www.marinemesse.or.jp/congress/schedule/",
        #"https://www.marinemesse.or.jp/congress/",
    ],
    "schema_version": "1.0",
    "selector_profile": "primary: table that has headers 各列『日時/イベント名/主催者』 / alt: any table with similar header",
    "pagination": {
        "next_selector": "a[rel='next'], .pagination a",
        "max_pages": 5,
    },
}

# ========= SELECTORS =========
SELECTORS = {
    "primary_table_match": ("日時", "イベント名", "主催者"),
    "alt_table_any": True,
}

# ========= 環境・共通 =========
JST = timezone(timedelta(hours=9))

def _split_and_normalize(s: str) -> str:
    if not s:
        return ""
    s = (
        s.replace(""", '"').replace(""", '"')
         .replace("'", "'").replace("'", "'")
         .replace("〜", "～").replace("―", "－")
    )
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _storage_path(date_str: str, code: str) -> Path:
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"

def _make_requests_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "event_notify (congress_b) / maintainer: your-contact",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.marinemesse.or.jp/",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    })
    retries = Retry(
        total=3,
        backoff_factor=0.7,
        status_forcelist=(403, 429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def _fetch_html(url: str, sess: requests.Session, timeout: float = 20.0) -> Optional[str]:
    try:
        r = sess.get(url, timeout=timeout)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", "") and r.text:
            return r.text
    except Exception:
        pass
    # fallback（任意）
    try:
        time.sleep(1.2)
        import cloudscraper  # type: ignore
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False, "desktop": True},
            delay=5
        )
        scraper.headers.update(sess.headers)
        r2 = scraper.get(url, timeout=timeout + 5)
        if r2.status_code == 200 and "text/html" in r2.headers.get("Content-Type", "") and r2.text:
            return r2.text
    except Exception:
        pass
    return None

# ========= パース =========
def _find_event_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    for t in soup.find_all("table"):
        header_text = _split_and_normalize(t.get_text(" ", strip=True))
        if all(key in header_text for key in SELECTORS["primary_table_match"]):
            return t
    tables = soup.find_all("table")
    return tables[0] if tables else None

def _parse_table(table: BeautifulSoup) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    rows = table.find_all("tr")
    if not rows:
        return events
    for tr in rows[1:]:
        tds = tr.find_all(["td", "th"])
        if len(tds) < 2:
            continue
        when_raw = _split_and_normalize(tds[0].get_text(" ", strip=True))
        title_cell = tds[1]
        a = title_cell.find("a")
        title_raw = _split_and_normalize(a.get_text(" ", strip=True) if a else title_cell.get_text(" ", strip=True))
        link = a.get("href") if a and a.has_attr("href") else None
        if not when_raw or not title_raw:
            continue
        if link and link.startswith("/"):
            link = "https://www.marinemesse.or.jp" + link
        events.append({"when": when_raw, "title": title_raw, "link": link or META["url_candidates"][0]})
    return events

# 🔥 新しい _materialize_events - parser.py を使用
def _materialize_events(rows: List[Dict[str, str]]) -> List[Dict]:
    base_year = datetime.now(JST).year
    out: List[Dict] = []
    
    for r in rows:
        when = r["when"]
        title = r["title"]
        source = r["link"]
        
        # 🎯 parser.py の split_and_normalize を使用
        parsed_events = split_and_normalize(when, title, META["venue"], base_year)
        
        for ev in parsed_events:
            item = {
                "schema_version": META["schema_version"],
                "date": ev["date"],
                "title": ev["title"],
                "venue": ev["venue"],
                "source": source,
            }
            
            # 時刻があれば追加
            if ev.get("time"):
                item["time"] = ev["time"]
            else:
                # 時刻未定の場合、元の文字列をnotesに保存
                item["notes"] = when
                
            out.append(item)
    
    return out

def _dedupe_and_hash(items: List[Dict]) -> List[Dict]:
    seen = set()
    norm_items: List[Dict] = []
    for ev in items:
        date = ev["date"]
        time_s = ev.get("time", "")
        title_norm = _split_and_normalize(ev["title"])
        venue_norm = _split_and_normalize(ev["venue"])
        key = f"{date}|{time_s}|{title_norm}|{venue_norm}"
        h = _sha1_hex(key)
        if h in seen:
            continue
        seen.add(h)
        ev["hash"] = h
        ev["extracted_at"] = datetime.now(JST).isoformat(timespec="seconds")
        norm_items.append(ev)
    def sort_key(e: Dict) -> Tuple:
        return (e["date"], e.get("time", "99:99"), _split_and_normalize(e["title"]))
    return sorted(norm_items, key=sort_key)

# ========= 今日抽出（新規） =========
def _resolve_target_date() -> str:
    """SCRAPER_TARGET_DATE=YYYY-MM-DD があればそれを優先。なければJSTの今日。"""
    override = os.getenv("SCRAPER_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")

def _filter_today_only(items: List[Dict], target_date: str) -> List[Dict]:
    return [e for e in items if e.get("date") == target_date]

# ========= メイン =========
def scrape_once(url: str, sess: requests.Session) -> List[Dict]:
    html = _fetch_html(url, sess)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    table = _find_event_table(soup)
    if not table:
        return []
    rows = _parse_table(table)
    items = _materialize_events(rows)
    return _dedupe_and_hash(items)

def main():
    t0 = time.time()
    sess = _make_requests_session()
    tried_urls: List[str] = []

    # 1) 収集（候補URLを順に）
    collected: List[Dict] = []
    for url in META["url_candidates"]:
        tried_urls.append(url)
        try:
            items = scrape_once(url, sess)
        except Exception as e:
            print(f"[{META['name']}][ERROR] msg=\"{e}\" url=\"{url}\"")
            items = []
        if items:
            collected = items
            break
        time.sleep(1.2)  # polite

    # 収集すらゼロ（HTML取れない/テーブル見つからない等）は"失敗扱い"で非生成
    if collected == [] and len(tried_urls) == len(META["url_candidates"]):
        elapsed_ms = int((time.time() - t0) * 1000)
        print(f"[{META['name']}][ERROR] msg=\"no events parsed\" tried={len(tried_urls)} ms={elapsed_ms}")
        return

    # 2) 今日抽出（既定）／全量保存（フラグ）
    target_date = _resolve_target_date()
    include_future = os.getenv("SCRAPER_INCLUDE_FUTURE") == "1"
    items_to_save = collected if include_future else _filter_today_only(collected, target_date)

    # 3) 保存（当日0件でも空配列を書き出す：監視の都合で成功扱い）
    outpath = _storage_path(target_date, META["code"])
    with outpath.open("w", encoding="utf-8") as f:
        json.dump(items_to_save, f, ensure_ascii=False, indent=2)

    # 4) ログ
    elapsed_ms = int((time.time() - t0) * 1000)
    print(f"[{META['name']}] date={target_date} items={len(items_to_save)} ms={elapsed_ms} include_future={int(include_future)}")

if __name__ == "__main__":
    main()
