# scrapers/marinemesse_b.py
import os, json, time, re
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from event_notify.utils.parser import split_and_normalize, JST
# NOTE: 追記仕様により STORAGE_DIR は使わず、常に repo直下の storage/ を解決
# from event_notify.utils.paths import STORAGE_DIR  # ← 不使用

DEBUG = os.getenv("DEBUG_B", "0") == "1"

URL = "https://www.marinemesse.or.jp/messe-b/event/"
VENUE = "マリンメッセB館"
VENUE_CODE = "b"  # 仕様の venue_code
SCHEMA_VERSION = "1.0"

HEADERS = {
    "User-Agent": "event_notify/1.0 (+https://example.com; contact=email@example.com)"
}

# セレクタを一元管理（優先→代替）
SELECTORS = {
    "table_primary": "table.table_list01",
    "table_fallback": "table",
    "title_anchor": "a",
    "th_like": "th, dt, .label, .ttl",
}

REQUEST_TIMEOUT = 15
RETRY_5XX = 3
RETRY_SLEEP_BASE = 1.0  # 指数バックオフの基点秒
DETAIL_REQUEST_SLEEP = 1.0  # マナー用の最小スリープ


def sha1(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _http_get(url: str, session: requests.Session) -> requests.Response:
    """5xxに対する指数バックオフ付きGET"""
    for i in range(RETRY_5XX + 1):
        r = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if 500 <= r.status_code < 600 and i < RETRY_5XX:
            time.sleep(RETRY_SLEEP_BASE * (2 ** i))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


def _extract_datetime_from_detail(url: str, session: requests.Session) -> str:
    """詳細ページから開催日時テキストを抽出し1本に束ねて返す"""
    try:
        time.sleep(DETAIL_REQUEST_SLEEP)
        r = _http_get(url, session)
        s = BeautifulSoup(r.text, "html.parser")

        # 優先: 「開催日時」「開催日」「日程」などの th/label を探す
        for th in s.select(SELECTORS["th_like"]):
            label = th.get_text(" ", strip=True)
            if any(k in label for k in ["開催日時", "開催日", "日程", "日時"]):
                td = th.find_next("td") or th.find_next("dd") or th.parent.find_next("td")
                if td:
                    text = td.get_text(" ", strip=True)
                    if text:
                        return re.sub(r"\s+", " ", text)

        # 次善: ページ全体から日付らしい行を拾う
        body_text = s.get_text(" ", strip=True)
        m = re.search(r"(\d{4}[./-]\d{1,2}[./-]\d{1,2}[^。\n]*?)", body_text)
        if m:
            return m.group(1)
        m2 = re.search(r"(\d{1,2}[./]\d{1,2}.*?(?:\d{1,2}:\d{2})?.*?)", body_text)
        if m2:
            return m2.group(1)

    except Exception as e:
        if DEBUG:
            print("[marinemesse_b][ERROR] detail:", repr(e))
    return ""


def fetch_raw_events(session: requests.Session) -> List[Dict[str, str]]:
    """
    B館は「1イベント = 複数tr」構成。
    日時は1列目に分割表示、タイトルは <a> のある行。
    """
    r = _http_get(URL, session)
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.select_one(SELECTORS["table_primary"]) or soup.select_one(SELECTORS["table_fallback"])
    if not table:
        return []

    events = []
    pending_datetime_lines: List[str] = []

    for tr in table.select("tr"):
        if tr.find("th"):
            continue
        tds = tr.find_all("td")
        if not tds:
            continue

        a = tr.select_one(SELECTORS["title_anchor"])
        if a and a.get_text(strip=True):
            title = a.get_text(" ", strip=True)

            # 直前まで貯めた日時テキストを束ねる
            datetime_text = " ".join(s for s in (t.strip() for t in pending_datetime_lines) if s)
            pending_datetime_lines = []

            # 当行1列目も Fallback
            if not datetime_text and tds:
                datetime_text = tds[0].get_text(" ", strip=True)

            # さらに空なら詳細ページ
            href = a.get("href")
            if href and href.startswith("/"):
                href = f"https://www.marinemesse.or.jp{href}"
            if not datetime_text and href:
                dt_from_detail = _extract_datetime_from_detail(href, session)
                if dt_from_detail:
                    datetime_text = dt_from_detail

            events.append({"datetime": datetime_text, "title": title})
            continue

        first_col_text = tds[0].get_text(" ", strip=True) if tds else ""
        if first_col_text:
            pending_datetime_lines.append(first_col_text)

    return events


def _resolve_target_date() -> str:
    """JST基準のターゲット日（上書き可）"""
    override = os.getenv("SCRAPER_TARGET_DATE")
    if override:
        return override  # YYYY-MM-DD 前提
    return datetime.now(JST).strftime("%Y-%m-%d")


def _storage_dir() -> Path:
    """
    追記仕様16: 必ず repo直下の storage/ に出力する。
    （このファイルは event_notify/scrapers/ 配下にある想定）
    """
    repo_root = Path(__file__).resolve().parents[1]  # event_notify/
    return repo_root / "storage"


def main():
    t0 = time.time()
    session = requests.Session()

    target_date = _resolve_target_date()
    include_future = os.getenv("SCRAPER_INCLUDE_FUTURE") == "1"

    raw = fetch_raw_events(session)

    # 正規化＆展開
    normalized: List[Dict[str, Any]] = []
    for e in raw:
        normalized.extend(split_and_normalize(e["datetime"], e["title"], VENUE))

    # today抽出（冗長化：dispatch側と二段構え）
    items_all = normalized
    items_today = items_all if include_future else [x for x in items_all if x.get("date") == target_date]

    # ハッシュ付与（date|time|title|venue）＆整列
    out: List[Dict[str, Any]] = []
    seen = set()
    extracted_at = datetime.now(JST).isoformat()
    for it in sorted(items_today, key=lambda x: (x.get("date", ""), x.get("time", "") or "99:99", x.get("title", ""))):
        key = f'{it.get("date","")}|{it.get("time","") or ""}|{it.get("title","")}|{it.get("venue","")}'
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

    # === 保存（追記仕様16に従い storage/直下に必ず保存。0件でも空配列 [] を保存） ===
    storage_dir = _storage_dir()
    storage_dir.mkdir(parents=True, exist_ok=True)
    path = storage_dir / f"{target_date}_{VENUE_CODE}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    ms = int((time.time() - t0) * 1000)
    print(f"[marinemesse_b] date={target_date} items={len(out)} ms={ms} path={path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 失敗時も“壊れない”を優先し、空配列を書き出して可観測化（追記仕様の方針）
        try:
            target_date = _resolve_target_date()
            storage_dir = _storage_dir()
            storage_dir.mkdir(parents=True, exist_ok=True)
            path = storage_dir / f"{target_date}_{VENUE_CODE}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print(f"[marinemesse_b][ERROR] {repr(e)} -> wrote empty file {path}")
        except Exception as e2:
            print(f"[marinemesse_b][FATAL] fallback write failed: {repr(e2)}")
