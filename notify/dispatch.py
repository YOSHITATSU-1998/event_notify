# notify/dispatch.py ぢすぱーち君（環境変数版・UTF-8保存）
import os
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any
import requests

from event_notify.utils.paths import STORAGE_DIR

# --- 設定 ---------------------------------------------------------------
JST = timezone(timedelta(hours=9))
VENUES: List[Tuple[str, str]] = [
    ("a", "マリンメッセA館"),
    ("b", "マリンメッセB館"),
    ("c", "福岡国際センター"),
    ("d", "福岡国際会議場"),
]
CODE_INDEX: Dict[str, int] = {c: i for i, (c, _) in enumerate(VENUES)}
CODE2NAME: Dict[str, str] = {c: n for c, n in VENUES}
LAST_SENT_PATH = (STORAGE_DIR / "last_sent.txt")

# ★ 環境変数から取得
def get_webhook_urls():
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    line_token = os.getenv("LINE_NOTIFY_TOKEN")
    
    if not slack_url:
        print("[dispatch][WARN] SLACK_WEBHOOK_URL not set")
    
    return slack_url, line_token

# --- ユーティリティ ------------------------------------------------------
def determine_today() -> str:
    override = os.getenv("DISPATCH_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")

def _read_json_array(path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return []

def _time_key(t: str | None) -> str:
    return t if (t and len(t) == 5) else "99:99"

def _sort_key(ev: Dict[str, Any]):
    return (_time_key(ev.get("time")), ev.get("title", ""), CODE_INDEX.get(ev.get("code",""), 10**9))

# --- コア ---------------------------------------------------------------
def load_events_for(today: str) -> tuple[list[Dict[str, Any]], list[str]]:
    all_ev: list[Dict[str, Any]] = []
    missing: list[str] = []

    for code, _name in VENUES:
        path = STORAGE_DIR / f"{today}_{code}.json"
        try:
            arr = _read_json_array(path)
        except FileNotFoundError:
            missing.append(code)
            continue
        except Exception as e:
            print(f"[dispatch][WARN] read fail code={code} msg=\"{e}\"")
            missing.append(code)
            continue

        for obj in arr:
            date = obj.get("date")
            title = obj.get("title")
            if not date or not title:
                continue
            if date != today:
                continue
            ev = {
                "date": date,
                "time": obj.get("time"),
                "title": title,
                "venue": obj.get("venue") or CODE2NAME.get(code, ""),
                "source": obj.get("source"),
                "hash": obj.get("hash"),
                "code": code,
            }
            all_ev.append(ev)

    seen: set[str] = set()
    uniq: list[Dict[str, Any]] = []
    for ev in all_ev:
        key = ev.get("hash") or f"{ev['date']}|{ev.get('time') or ''}|{ev['title']}|{ev['venue']}"
        if key in seen:
            continue
        seen.add(key)
        uniq.append(ev)

    uniq.sort(key=_sort_key)
    return uniq, missing

# --- 整形 ---------------------------------------------------------------
def format_message(today: str, events: list[Dict[str, Any]], missing: list[str]) -> str:
    lines: list[str] = [f"【本日のイベント】{today}"]

    if not events:
        lines.append("本日の掲載イベントは見つかりませんでした。")
    else:
        for ev in events:
            t = ev.get("time") if ev.get("time") else "（時刻未定）"
            lines.append(f"- {t}｜{ev.get('title','')}（{ev.get('venue','')}）")

    if missing:
        lines.append("取得できなかった会場: " + ", ".join(missing))

    return "\n".join(lines)

# --- 再送防止（保存だけ残す） --------------------------------------------
def _body_sha1(body: str) -> str:
    return hashlib.sha1(body.encode("utf-8")).hexdigest()

def save_body_hash(body: str) -> None:
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LAST_SENT_PATH, "w", encoding="utf-8") as f:
            f.write(_body_sha1(body))
    except Exception as e:
        print(f"[dispatch][WARN] last_sent write fail msg=\"{e}\"")

# --- 送信 ---------------------------------------------------------------
def send_to_slack(text: str, webhook_url: str) -> bool:
    if not webhook_url:
        print("[dispatch][WARN] No Slack URL -> skip Slack")
        return False
    try:
        r = requests.post(webhook_url, json={"text": text}, timeout=15)
        print(f"[dispatch] slack status={r.status_code}")
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[dispatch][ERROR] Slack msg=\"{e}\"")
        return False

def send_to_line(text: str, line_token: str) -> bool:
    if not line_token:
        return False
    try:
        r = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {line_token}"},
            data={"message": text},
            timeout=15,
        )
        print(f"[dispatch] line status={r.status_code}")
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[dispatch][ERROR] LINE msg=\"{e}\"")
        return False

# --- build_message 関数（Web出力と共用） ----------------------------------
def build_message(today: str, events: list[Dict[str, Any]], missing: list[str]) -> str:
    """Slack通知とWeb出力で共用する純関数"""
    return format_message(today, events, missing)

# --- main ----------------------------------------------------------------
def main() -> None:
    print("[dispatch] start")
    today = determine_today()
    events, missing = load_events_for(today)
    print(f"[dispatch] gathered items={len(events)} missing={missing}")

    body = build_message(today, events, missing)
    print("[dispatch] preview:\n" + body)

    # ★ 環境変数から取得
    slack_url, line_token = get_webhook_urls()

    # 送信実行
    sent = False
    sent = send_to_slack(body, slack_url) or sent
    sent = send_to_line(body, line_token) or sent

    print(f"[dispatch] sent={sent}")
    if sent:
        save_body_hash(body)

if __name__ == "__main__":
    main()