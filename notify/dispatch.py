# notify/dispatch.py Ver.3.4.2対応版（実行ログ通知専用 + DBカウント）
import os
import sys
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Optional
import requests

# パス解決
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# --- 設定 ---------------------------------------------------------------
JST = timezone(timedelta(hours=9))
VENUES: List[Tuple[str, str]] = [
    ("a", "マリンメッセA館"),
    ("b", "マリンメッセB館"),
    ("c", "福岡国際センター"),
    ("d", "福岡国際会議場"),
    ("e", "福岡サンパレス"),
    ("f", "みずほPayPayドーム"),
    ("f_event", "みずほPayPayドーム（イベント）"),
    ("g", "ベスト電器スタジアム")
]
CODE_INDEX: Dict[str, int] = {c: i for i, (c, _) in enumerate(VENUES)}
CODE2NAME: Dict[str, str] = {c: n for c, n in VENUES}

# 表示用: PayPayドーム(野球)とPayPay(イベント)はDB上で同一venue名のため合算表示
DISPLAY_VENUES: List[Tuple[str, str]] = [(c, n) for c, n in VENUES if c != "f_event"]

# ★ 環境変数から取得
def get_webhook_urls():
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    if not slack_url:
        print("[dispatch][WARN] SLACK_WEBHOOK_URL not set")
    return slack_url

# --- ユーティリティ ------------------------------------------------------
def determine_today() -> str:
    override = os.getenv("DISPATCH_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")

def _shorten_venue_name(name: str) -> str:
    """会場名を省略形に変換"""
    if "マリンメッセ" in name:
        return name.replace("マリンメッセ", "")
    elif "福岡国際センター" in name:
        return "国際センター"
    elif "福岡国際会議場" in name:
        return "国際会議場"
    elif "福岡サンパレス" in name:
        return "サンパレス"
    elif "みずほPayPayドーム（イベント）" in name:
        return "PayPay(イベ)"
    elif "みずほPayPayドーム" in name:
        return "PayPayドーム"
    elif "ベスト電器スタジアム" in name:
        return "ベスト電器S"
    return name

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

# --- DB件数取得 -----------------------------------------------------------
def get_db_counts(today: str) -> Optional[dict]:
    """Supabaseから会場ごとの件数を取得。失敗時はNoneを返す。"""
    # ENABLE_DB_SAVE=0 の場合はスキップ
    if os.getenv("ENABLE_DB_SAVE", "0") != "1":
        print("[dispatch] ENABLE_DB_SAVE=0 -> DB counts skipped")
        return None

    try:
        from supabase import create_client
        from collections import Counter

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            print("[dispatch][WARN] Missing SUPABASE credentials -> DB counts skipped")
            return None

        supabase = create_client(supabase_url, supabase_key)

        result = supabase.table('events')\
            .select('venue')\
            .eq('event_type', 'auto')\
            .gte('date', today)\
            .execute()

        # venue名→コード変換用逆引き辞書
        NAME2CODE = {v: k for k, v in CODE2NAME.items()}

        counter = Counter(row['venue'] for row in result.data)

        db_counts = {}
        for venue_name, count in counter.items():
            code = NAME2CODE.get(venue_name)
            if code:
                db_counts[code] = count

        print(f"[dispatch] DB counts retrieved: {sum(db_counts.values())} total")
        return db_counts

    except Exception as e:
        print(f"[dispatch][WARN] Failed to get DB counts: {e}")
        return None

# --- メッセージ生成 ------------------------------------------------------
def get_east_asian_width_count(text: str) -> int:
    """全角文字を2、半角文字を1として文字幅を計算する"""
    count = 0
    for c in text:
        if unicodedata.east_asian_width(c) in 'FWA':
            count += 2
        else:
            count += 1
    return count

def _format_venue_line(short_name: str, count: int, warn: bool = False) -> str:
    """会場1行分の整形"""
    width = get_east_asian_width_count(short_name)
    padding = max(0, 16 - width)
    formatted_name = short_name + " " * padding
    status_icon = "✅" if count > 0 else "⚠️"
    if warn:
        status_icon = "⚠️"
    return f"{formatted_name}: {count:3}件 {status_icon}"

def _merge_paypay_counts(counts: dict) -> dict:
    """f(野球)とf_event(イベント)を合算してfに統合"""
    merged = dict(counts)
    merged["f"] = merged.get("f", 0) + merged.get("f_event", 0)
    merged.pop("f_event", None)
    return merged

def _build_section(title: str, counts: dict, venues_list=None, compare_counts: Optional[dict] = None) -> list:
    """スクレイプ件数 or DB件数セクションを生成"""
    if venues_list is None:
        venues_list = VENUES
    lines = [f"\n--- {title} ---"]
    total = 0
    for code, name in venues_list:
        count = counts.get(code, 0)
        total += count
        short_name = _shorten_venue_name(name)
        # 比較対象がある場合、差異があれば⚠️
        warn = False
        if compare_counts is not None:
            compare_count = compare_counts.get(code, 0)
            if count != compare_count:
                warn = True
        lines.append(_format_venue_line(short_name, count, warn))
    lines.append(f"合計: {total}件")
    return lines

def build_log_message(today: str, venue_counts: dict, db_counts: Optional[dict] = None) -> str:
    """件数ログメッセージを生成する純関数"""
    current_time = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    lines = [f"【実行ログ】{current_time}"]

    # スクレイプ件数セクション（全8会場そのまま表示）
    lines.extend(_build_section("スクレイプ件数", venue_counts, venues_list=VENUES))

    # DB件数セクション（PayPay合算、f_event行なし）
    if db_counts is not None:
        merged_db = _merge_paypay_counts(db_counts)
        merged_scrape_for_compare = _merge_paypay_counts(venue_counts)
        lines.extend(_build_section("DB件数", merged_db, venues_list=DISPLAY_VENUES, compare_counts=merged_scrape_for_compare))
    elif os.getenv("ENABLE_DB_SAVE", "0") != "1":
        lines.append("\n--- DB件数 ---")
        lines.append("N/A（ENABLE_DB_SAVE=0）")
    else:
        lines.append("\n--- DB件数 ---")
        lines.append("⚠️ 取得失敗")

    return "\n".join(lines)

# --- エントリポイント ------------------------------------------------------
def send_log(venue_counts: dict) -> None:
    """refresh_future_events.pyから呼び出すエントリポイント"""
    today = determine_today()

    # DB件数を取得（内部で自己完結）
    db_counts = get_db_counts(today)

    body = build_log_message(today, venue_counts, db_counts)
    print("[dispatch] preview:\n" + body)

    # DRY_RUN チェック
    if os.getenv("DRY_RUN") == "1":
        print("[dispatch] DRY_RUN mode - not sending")
        return

    slack_url = get_webhook_urls()

    # 送信実行
    sent = send_to_slack(body, slack_url)
    print(f"[dispatch] sent={sent}")

if __name__ == "__main__":
    print("[dispatch] 単体実行は非対応。refresh_future_events.py経由で実行してください。")
