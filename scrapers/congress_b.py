# scrapers/congress_b.py Ver.3.0 — Studio Design CMS API対応
# 福岡国際会議場（思い出ネーム: コングレスB）
# 出力：storage/{date}_d.json（schema_version=1.0）
from utils.marinemesse_api import run_venue_scraper

META = {
    "name": "congress_b",
    "venue": "福岡国際会議場",
    "code": "d",
    "filter_id": "lIUXZkl6",
    "source_url": "https://www.marinemesse.or.jp/congress/event/",
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
