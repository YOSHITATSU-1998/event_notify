# notify/html_export.py Ver.1.6対応版（スマホファースト・2行表示対応）
import os
import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Tuple, Dict, Any

# パス解決
sys.path.append(str(Path(__file__).parent.parent))

# JST定義
JST = timezone(timedelta(hours=9))

# 会場定義（ハードコード）
VENUES = [
    ("a", "マリンメッセA館"),
    ("b", "マリンメッセB館"),
    ("c", "福岡国際センター"),
    ("d", "福岡国際会議場"),
    ("e", "福岡サンパレス"),
    ("f", "みずほPayPayドーム"),
    ("f_event", "みずほPayPayドーム（イベント）"),  
    ("g","ベスト電器スタジアム")#1.6実装
]

# 会場リンクマッピング
VENUE_LINKS = {
    "マリンメッセA館": "https://www.marinemesse.or.jp/messe/event/",
    "マリンメッセB館": "https://www.marinemesse.or.jp/messe-b/event/",
    "福岡国際センター": "https://www.marinemesse.or.jp/kokusai/event/",
    "福岡国際会議場": "https://www.marinemesse.or.jp/congress/event/",
    "福岡サンパレス": "https://www.f-sunpalace.com/hall/#hallEvent",
    "みずほPayPayドーム": "https://www.softbankhawks.co.jp/",
    "ベスト電器スタジアム": "https://www.avispa.co.jp/game_practice"
}

# Google Forms URL
OPINION_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfX2EtHu3hZ2FgMfUjSOx1YYQqt2BaB3BGniVPF5TMCtgLByw/viewform"

def determine_today_standalone() -> str:
    """今日の日付を取得（単独動作版）"""
    return datetime.now(JST).strftime("%Y-%m-%d")

def get_storage_dir() -> Path:
    """ストレージディレクトリを取得（単独動作版）"""
    try:
        from utils.paths import STORAGE_DIR
        return STORAGE_DIR
    except ImportError:
        storage_dir = Path(__file__).parent.parent / "storage"
        storage_dir.mkdir(exist_ok=True)
        return storage_dir

def load_events_standalone(today: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """イベントデータを読み込み（完全単独版）"""
    storage_dir = get_storage_dir()
    events = []
    missing = []
    
    print(f"[html_export] Loading events from: {storage_dir}")
    
    for code, venue_name in VENUES:
        json_path = storage_dir / f"{today}_{code}.json"
        
        try:
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # リスト形式の場合
                if isinstance(data, list):
                    events.extend(data)
                    print(f"[html_export] Loaded {len(data)} events from {code}")
                # 単一オブジェクトの場合
                elif isinstance(data, dict):
                    events.append(data)
                    print(f"[html_export] Loaded 1 event from {code}")
                else:
                    print(f"[html_export] Unexpected data format in {code}: {type(data)}")
            else:
                missing.append(code)
                print(f"[html_export] Missing file: {json_path}")
                
        except Exception as e:
            missing.append(code)
            print(f"[html_export] Error loading {code}: {e}")
    
    # 今日のイベントのみフィルタ
    today_events = [ev for ev in events if ev.get("date") == today]
    
    # 時刻順ソート
    def sort_key(event):
        time_str = event.get("time", "99:99")
        if not time_str or time_str == "（時刻未定）":
            return ("99:99", event.get("title", ""), event.get("venue", ""))
        return (time_str, event.get("title", ""), event.get("venue", ""))
    
    today_events.sort(key=sort_key)
    
    print(f"[html_export] Filtered to {len(today_events)} events for {today}")
    return today_events, missing

def build_message_standalone(today: str, events: List[Dict[str, Any]], missing: List[str]) -> str:
    """Ver.1.6: Slack通知と同じメッセージを生成（スマホファースト・2行表示対応）"""
    lines = [f"【本日のイベント】{today}"]
    
    if not events:
        lines.append("")  # タイトルとの区切り
        lines.append("本日の掲載イベントは見つかりませんでした。")
    else:
        lines.append("")  # タイトルとイベント一覧の区切り
        for i, ev in enumerate(events):
            time_str = ev.get("time", "（時刻未定）")
            title = ev.get("title", "")
            venue = ev.get("venue", "")
            
            # Ver.1.6: 2行表示
            lines.append(f"- {time_str}｜{venue}")
            lines.append(title)
            
            # 最後のイベント以外に空白行追加
            if i != len(events) - 1:
                lines.append("")

    if missing:
        lines.append("")  # イベントとmissing情報の区切り
        lines.append(f"取得できなかった会場: {', '.join(missing)}")

    # Ver.1.6: GitHub Pagesでは詳細URL不要（自分のページだから）
    
    return "\n".join(lines)

def generate_venue_list() -> str:
    """VENUES配列から会場一覧HTMLを生成（リンク化・PayPayドーム統合）"""
    # PayPayドーム重複削除
    unique_venues = []
    seen_venues = set()
    
    for code, name in VENUES:
        # PayPayドーム系は統合
        if "みずほPayPayドーム" in name:
            if "みずほPayPayドーム" not in seen_venues:
                unique_venues.append("みずほPayPayドーム")
                seen_venues.add("みずほPayPayドーム")
        else:
            if name not in seen_venues:
                unique_venues.append(name)
                seen_venues.add(name)
    
    # リンク化してHTML生成
    lines = ["【現在の対応会場】"]
    for venue_name in unique_venues:
        if venue_name in VENUE_LINKS:
            url = VENUE_LINKS[venue_name]
            lines.append(f'・<a href="{url}" target="_blank" class="venue-link">{venue_name}</a>')
        else:
            lines.append(f"・{venue_name}")
    
    return "\n".join(lines)

def create_html_content(today: str, event_message: str, venue_list: str) -> str:
    """HTML全体を生成（意見箱セクション追加）"""
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
            margin-bottom: 30px;
        }}
        .venue-link {{
            color: #2980b9;
            text-decoration: none;
            transition: color 0.3s ease;
        }}
        .venue-link:hover {{
            color: #3498db;
            text-decoration: underline;
        }}
        .opinion-section {{
            background: #fff5cd;
            padding: 20px;
            border-radius: 5px;
            border-left: 4px solid #f39c12;
            text-align: center;
            margin-bottom: 30px;
        }}
        .opinion-link {{
            display: inline-block;
            background: #f39c12;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 16px;
            transition: background-color 0.3s ease;
            margin-top: 10px;
        }}
        .opinion-link:hover {{
            background: #e67e22;
            text-decoration: none;
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
            .opinion-link {{
                font-size: 14px;
                padding: 10px 20px;
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
        
        <div class="opinion-section">
            <h3>ご意見・ご要望</h3>
            <p>会場追加のご希望や情報漏れのご報告をお待ちしています</p>
            <a href="{OPINION_FORM_URL}" target="_blank" class="opinion-link">ご意見・ご要望はこちら</a>
            <p style="font-size: 0.8em; color: #666; margin-top: 10px;">
                ※ Googleアカウントが必要です
            </p>
        </div>
        
        <div class="footer">
            <p>福岡市内主要イベント会場の情報を自動収集・配信しています</p>
            <p>Ver.1.6 - 7会場対応（スマホファースト対応）</p>
        </div>
    </div>
</body>
</html>"""
    return html

def export_html():
    """HTMLファイルを生成してsite/index.htmlに保存（完全単独版）"""
    try:
        print("[html_export] Starting Ver.1.6 HTML generation (mobile-friendly mode)...")
        
        # 今日の日付を取得
        today = determine_today_standalone()
        print(f"[html_export] Target date: {today}")
        
        # イベントデータを読み込み（完全単独版）
        events, missing = load_events_standalone(today)
        print(f"[html_export] Loaded {len(events)} events, missing: {missing}")
        
        # メッセージ生成（Ver.1.6: スマホファースト対応）
        event_message = build_message_standalone(today, events, missing)
        print(f"[html_export] Generated mobile-friendly message: {len(event_message)} characters")
        
        # 会場一覧を生成（リンク化・統合処理）
        venue_list = generate_venue_list()
        print(f"[html_export] Generated venue list with links")
        
        # HTML全体を構築
        html_content = create_html_content(today, event_message, venue_list)
        
        # site/index.html に保存
        site_dir = Path(__file__).parent.parent / "site"
        site_dir.mkdir(exist_ok=True)
        output_path = site_dir / "index.html"
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"[html_export] Successfully generated: {output_path}")
        print(f"[html_export] File size: {len(html_content)} bytes")
        print(f"[html_export] Events included: {len(events)}")
        print(f"[html_export] Missing venues: {missing}")
        
    except Exception as e:
        print(f"[html_export][ERROR] Failed to generate HTML: {e}")
        import traceback
        traceback.print_exc()
        raise

def main():
    """メイン実行関数"""
    export_html()

if __name__ == "__main__":
    main()
