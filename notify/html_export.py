# notify/html_export.py Ver.1.3対応版（会場一覧付きHTML生成）
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# パス解決
sys.path.append(str(Path(__file__).parent.parent))
try:
    from utils.paths import STORAGE_DIR
except ImportError:
    STORAGE_DIR = Path(__file__).parent.parent / "storage"
    STORAGE_DIR.mkdir(exist_ok=True)

try:
    from notify.dispatch import load_events_for, determine_today, build_message, JST, VENUES
except ImportError:
    # フォールバック定義
    JST = datetime.now().astimezone().tzinfo
    VENUES = [
        ("a", "マリンメッセA館"),
        ("b", "マリンメッセB館"),
        ("c", "福岡国際センター"),
        ("d", "福岡国際会議場"),
        ("e", "福岡サンパレス"),
        ("f", "みずほPayPayドーム"),
    ]

# サイトディレクトリ
SITE_DIR = Path(__file__).parent.parent / "site"
SITE_DIR.mkdir(exist_ok=True)

def generate_venue_list() -> str:
    """VENUES配列から会場一覧HTMLを生成"""
    lines = ["【現在の対応会場】"]
    for code, name in VENUES:
        lines.append(f"・{name}")
    return "\n".join(lines)

def create_html_content(today: str, event_message: str, venue_list: str) -> str:
    """HTML全体を生成"""
    current_time = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>福岡イベント情報 - {today}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP", sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            background-color: #f8f9fa;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 10px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
        }}
        .update-time {{
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
            margin-bottom: 30px;
        }}
        .content {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
        }}
        pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace;
            font-size: 14px;
            line-height: 1.5;
            color: #2c3e50;
            margin: 0;
        }}
        .venue-section {{
            background: #e8f4fd;
            padding: 20px;
            border-radius: 5px;
            border-left: 4px solid #3498db;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            color: #95a5a6;
            font-size: 0.85em;
        }}
        @media (max-width: 600px) {{
            body {{
                padding: 10px;
            }}
            .container {{
                padding: 15px;
            }}
            pre {{
                font-size: 13px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>福岡イベント情報</h1>
        <div class="update-time">最終更新: {current_time}</div>
        
        <div class="content">
            <pre>{event_message}</pre>
        </div>
        
        <div class="venue-section">
            <pre>{venue_list}</pre>
        </div>
        
        <div class="footer">
            <p>福岡市内主要イベント会場の情報を自動収集・配信しています</p>
            <p>Ver.1.3 - 6会場対応</p>
        </div>
    </div>
</body>
</html>"""
    return html

def export_html():
    """HTMLファイルを生成してsite/index.htmlに保存"""
    try:
        print("[html_export] Starting Ver.1.3 HTML generation...")
        
        # 今日の日付を取得
        today = determine_today()
        print(f"[html_export] Target date: {today}")
        
        # イベントデータを読み込み
        try:
            from notify.dispatch import load_events_for
            events, missing = load_events_for(today)
            print(f"[html_export] Loaded {len(events)} events, missing: {missing}")
        except ImportError:
            print("[html_export] Could not import dispatch functions, using empty data")
            events, missing = [], []
        
        # Slack通知と同じメッセージを生成
        try:
            from notify.dispatch import build_message
            event_message = build_message(today, events, missing)
        except ImportError:
            # フォールバック
            if not events:
                event_message = f"【本日のイベント】{today}\n本日の掲載イベントは見つかりませんでした。"
            else:
                lines = [f"【本日のイベント】{today}"]
                for ev in events:
                    time_str = ev.get("time", "（時刻未定）")
                    title = ev.get("title", "")
                    venue = ev.get("venue", "")
                    lines.append(f"- {time_str}｜{title}（{venue}）")
                event_message = "\n".join(lines)
        
        print(f"[html_export] Generated message: {len(event_message)} characters")
        
        # 会場一覧を生成
        venue_list = generate_venue_list()
        print(f"[html_export] Generated venue list: {len(VENUES)} venues")
        
        # HTML全体を構築
        html_content = create_html_content(today, event_message, venue_list)
        
        # site/index.html に保存
        output_path = SITE_DIR / "index.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"[html_export] Successfully generated: {output_path}")
        print(f"[html_export] File size: {len(html_content)} bytes")
        
    except Exception as e:
        print(f"[html_export][ERROR] Failed to generate HTML: {e}")
        raise

def main():
    """メイン実行関数"""
    export_html()

if __name__ == "__main__":
    main()
