"""
毎営業日 15:40 JST頃に実行(daily_price_update.ymlから呼び出す)。
前営業日に決算があった掲載銘柄について、本日(=決算翌営業日)の場中高値・その時刻・終値を記録する。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pts_common import fetch_stock_page, get_today_session_table, jst_today, prev_business_day  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
CALENDAR_PATH = DATA_DIR / "calendar_data.json"
LOG_PATH = DATA_DIR / "pts_detail_log.json"


def main():
    today = jst_today()
    target = prev_business_day(today)
    target_str = target.strftime("%Y%m%d")

    calendar = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    items = calendar["days"].get(target_str, [])

    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.exists() else {}
    day_log = log.setdefault(target_str, {})

    for item in items:
        code = item["code"]
        entry = day_log.setdefault(code, {"name": item["name"]})
        soup = fetch_stock_page(code)
        if soup is None:
            print(f"{code}: ページ取得失敗", file=sys.stderr)
            continue
        session = get_today_session_table(soup)
        if not session:
            print(f"{code}: 場中データなし", file=sys.stderr)
            continue
        if "高値" in session:
            entry["nextDayHigh"] = session["高値"]["price"]
            entry["nextDayHighTime"] = session["高値"]["time"]
        if "終値" in session:
            entry["nextDayClose"] = session["終値"]["price"]
        print(f"{code}: {entry}", file=sys.stderr)

    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(day_log)} entries for {target_str} (next-day session)", file=sys.stderr)


if __name__ == "__main__":
    main()
