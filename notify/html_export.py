# notify/html_export.py - Web公開用HTML生成
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# dispatch.pyから必要な関数をインポート
from event_notify.notify.dispatch import determine_today, load_events_for, format_message

# --- 設定 ---------------------------------------------------------------
JST = timezone(timedelta(hours=9))
SITE_DIR = Path("site")

def generate_html(today: str, slack_text: str) -> str:
    """SlackテキストをHTMLに変換"""
    
    # GitHub PagesのURL（リポジトリ名は環境変数から取得、なければデフォルト）
    repo_name = os.getenv("GITHUB_REPOSITORY", "your-repo/event_notify")
    pages_url = f"https://{repo_name.split('/')[0]}.github.io/{repo_name.split('/')[1]}"
    
    # 現在時刻
    generated_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    
    # HTMLテンプレート
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>福岡イベント情報 - {today}</title>
    <style>
        body {{
            font-family: 'Hiragino Sans', 'Hiragino Kaku Gothic ProN', Meiryo, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            color: #333;
        }}
        .content {{
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-wrap;
            font-family: 'Consolas', 'Monaco', monospace;
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 4px;
            border: 1px solid #e9ecef;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>福岡イベント情報</h1>
            <p>最終更新: {generated_at}</p>
        </div>
        
        <div class="content">{slack_text}</div>
        
        <div class="footer">
            <p>このページは自動生成されています</p>
            <p><a href="{pages_url}">{pages_url}</a></p>
        </div>
    </div>
</body>
</html>"""
    
    return html

def export_html() -> bool:
    """HTMLファイルを生成してsite/index.htmlに保存"""
    try:
        print("[html_export] start")
        
        # 今日の日付を取得
        today = determine_today()
        
        # イベントデータを読み込み
        events, missing = load_events_for(today)
        print(f"[html_export] items={len(events)} missing={missing}")
        
        # Slackと同じメッセージを生成
        slack_text = format_message(today, events, missing)
        
        # HTMLを生成
        html_content = generate_html(today, slack_text)
        
        # site/ディレクトリを作成
        SITE_DIR.mkdir(exist_ok=True)
        
        # index.htmlに保存
        output_path = SITE_DIR / "index.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"[html_export] generated {output_path}")
        return True
        
    except Exception as e:
        print(f"[html_export][ERROR] msg=\"{e}\"")
        return False

def main():
    """メイン実行関数"""
    success = export_html()
    if success:
        print("[html_export] complete")
    else:
        print("[html_export] failed")

if __name__ == "__main__":
    main()