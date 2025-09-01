from pathlib import Path

# event_notify パッケージのルート
BASE_DIR = Path(__file__).resolve().parents[1]
# ここに統一して保存/読込する
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
