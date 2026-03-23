# scrapers/kokusai_center.py Ver.3.0 — Studio Design CMS API対応
# 出力：storage/{date}_c.json（schema_version=1.0）
from utils.marinemesse_api import run_venue_scraper

META = {
    "name": "kokusai_center",
    "venue": "福岡国際センター",
    "code": "c",
    "filter_id": "E_9DjhIA",
    "source_url": "https://www.marinemesse.or.jp/kokusai/event/",
    "schema_version": "1.0",
}


def main():
    run_venue_scraper(META)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        msg = str(e).replace("\n", " ").strip()
        print(f"[{META['name']}][ERROR] msg=\"{msg}\" url=\"{META['source_url']}\"")
