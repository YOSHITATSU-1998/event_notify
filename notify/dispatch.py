# notify/dispatch.py Ver.3.3対応版（実行ログ通知専用）
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict
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

# --- メッセージ生成 ------------------------------------------------------
import unicodedata

def get_east_asian_width_count(text: str) -> int:
    """全角文字を2、半角文字を1として文字幅を計算する"""
    count = 0
    for c in text:
        if unicodedata.east_asian_width(c) in 'FWA':
            count += 2
        else:
            count += 1
    return count

def build_log_message(today: str, venue_counts: dict) -> str:
    """件数ログメッセージを生成する純関数"""
    current_time = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    lines = [f"【実行ログ】{current_time}"]
    
    # 整形用フォーマット: 最長の会場名に合わせてパディング
    # 全角文字と半角文字が混在するため概算の幅合わせ
    total_count = 0
    for code, name in VENUES:
        count = venue_counts.get(code, 0)
        total_count += count
        
        # 0件の場合は⚠️マーク
        status_icon = "✅" if count > 0 else "⚠️"
        
        # 名前を省略して揃える（例：マリンメッセA館 -> A館）
        short_name = name
        if "マリンメッセ" in name:
            short_name = name.replace("マリンメッセ", "")
        elif "福岡国際センター" in name:
            short_name = "国際センター"
        elif "福岡国際会議場" in name:
            short_name = "国際会議場"
        elif "福岡サンパレス" in name:
            short_name = "サンパレス"
        elif "みずほPayPayドーム（イベント）" in name:
            short_name = "PayPay(イベ)"
        elif "みずほPayPayドーム" in name:
            short_name = "PayPayドーム"
        elif "ベスト電器スタジアム" in name:
            short_name = "ベスト電器S"
            
        # 16文字分でパディング（全角/半角混合対応）
        width = get_east_asian_width_count(short_name)
        padding = max(0, 16 - width)
        formatted_name = short_name + " " * padding
        lines.append(f"{formatted_name}: {count:3}件 {status_icon}")
        
    lines.append("─────────────")
    lines.append(f"合計: {total_count}件")
    
    return "\n".join(lines)

# --- エントリポイント ------------------------------------------------------
def send_log(venue_counts: dict) -> None:
    """refresh_future_events.pyから呼び出すエントリポイント"""
    today = determine_today()
    body = build_log_message(today, venue_counts)
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
    # 単体テスト用
    dummy_counts = {"a": 35, "b": 24, "c": 14, "d": 46, "e": 12, "f": 8, "f_event": 6, "g": 3}
    send_log(dummy_counts)
