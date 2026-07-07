"""
本日決算があった「当ツール掲載銘柄」(=イチオシ決算で過去に言及されており、かつ
本日決算発表予定として掲載されている銘柄)の夜間PTS価格を取得し、
docs/data/pts_log.json に日付ごとに追記保存する(過去分は上書きせず全て残す)。

平日の夜(場中終了後、PTS取引時間帯)に実行する想定。
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
CALENDAR_PATH = DATA_DIR / "calendar_data.json"
LOG_PATH = DATA_DIR / "pts_log.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch_pts(code: str):
    url = f"https://kabutan.jp/stock/?code={code}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    close_span = soup.select_one("span.kabuka")
    close_price = None
    if close_span:
        m = re.search(r"([\d,]+)", close_span.get_text())
        if m:
            close_price = float(m.group(1).replace(",", ""))

    pts_label = soup.find("div", class_="kabuka1", string=re.compile("PTS"))
    if pts_label is None:
        return None
    pts_price_div = pts_label.find_next_sibling("div", class_="kabuka2")
    pts_time_div = pts_price_div.find_next_sibling("div", class_="kabuka3") if pts_price_div else None
    if pts_price_div is None:
        return None
    m = re.search(r"([\d,]+)", pts_price_div.get_text())
    if not m:
        return None
    pts_price = float(m.group(1).replace(",", ""))
    pts_time = pts_time_div.get_text(strip=True) if pts_time_div else None

    change_pct = None
    if close_price:
        change_pct = round((pts_price - close_price) / close_price * 100, 2)

    return {
        "pts": pts_price,
        "ptsTime": pts_time,
        "close": close_price,
        "changeFromClose": change_pct,
    }


def main():
    today_str = date.today().strftime("%Y%m%d")
    calendar = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    todays_items = calendar["days"].get(today_str, [])

    if not todays_items:
        print(f"{today_str}: 本日決算の掲載銘柄なし", file=sys.stderr)

    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.exists() else {}
    day_log = log.setdefault(today_str, {})

    for item in todays_items:
        code = item["code"]
        result = fetch_pts(code)
        if result:
            day_log[code] = {"name": item["name"], **result}
            print(f"{code} {item['name']}: {result}", file=sys.stderr)
        else:
            print(f"{code} {item['name']}: PTSデータ取得できず", file=sys.stderr)

    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(day_log)} entries for {today_str} (total dates in log: {len(log)})", file=sys.stderr)


if __name__ == "__main__":
    main()
