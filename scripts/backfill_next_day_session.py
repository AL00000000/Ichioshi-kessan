"""
一回限りのバックフィル用スクリプト。
ライブページの場中スナップショットがすでにローテーションしてしまった日付について、
株探の時系列株価(日足)テーブルから 高値・終値 を補完する(発表時刻は取得不可のため空)。
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
CALENDAR_PATH = DATA_DIR / "calendar_data.json"
LOG_PATH = DATA_DIR / "pts_detail_log.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch_daily_high_close(code: str, target_date: str, max_pages: int = 3):
    for page in range(1, max_pages + 1):
        url = f"https://kabutan.jp/stock/kabuka?code={code}&ashi=day&page={page}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            break
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        for tr in soup.select("tr"):
            th = tr.find("th")
            time_tag = th.find("time") if th else None
            if not time_tag or not time_tag.get("datetime"):
                continue
            dstr = time_tag["datetime"].replace("-", "")
            if dstr != target_date:
                continue
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            try:
                high = float(tds[1].get_text(strip=True).replace(",", ""))
                close = float(tds[3].get_text(strip=True).replace(",", ""))
            except ValueError:
                return None
            return {"high": high, "close": close}
    return None


def business_day_after(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def main():
    target_earnings_dates = sys.argv[1:] or ["20260707"]

    calendar = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.exists() else {}

    for earnings_date in target_earnings_dates:
        items = calendar["days"].get(earnings_date, [])
        next_day = business_day_after(date(
            int(earnings_date[0:4]), int(earnings_date[4:6]), int(earnings_date[6:8])
        )).strftime("%Y%m%d")

        day_log = log.setdefault(earnings_date, {})
        for item in items:
            code = item["code"]
            result = fetch_daily_high_close(code, next_day)
            entry = day_log.setdefault(code, {"name": item["name"]})
            if result:
                entry.setdefault("nextDayHigh", result["high"])
                entry.setdefault("nextDayClose", result["close"])
                entry["nextDayHighTime"] = entry.get("nextDayHighTime")  # 取得不可
                print(f"{earnings_date} {code}: {result}", file=sys.stderr)
            else:
                print(f"{earnings_date} {code}: データなし({next_day})", file=sys.stderr)

    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
