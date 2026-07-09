"""
毎平日 17:20 JST頃に実行。
本日決算があった「当ツール掲載銘柄」について、夜間PTSの始値と(この時点までの)高値を記録する。
docs/data/pts_detail_log.json に日付・銘柄コードごとに保存する(既存の値は上書きしない)。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pts_common import fetch_stock_page, get_pts_table, jst_today  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
CALENDAR_PATH = DATA_DIR / "calendar_data.json"
LOG_PATH = DATA_DIR / "pts_detail_log.json"


def main():
    today_str = jst_today().strftime("%Y%m%d")
    calendar = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    items = calendar["days"].get(today_str, [])

    log = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.exists() else {}
    day_log = log.setdefault(today_str, {})

    for item in items:
        code = item["code"]
        entry = day_log.setdefault(code, {"name": item["name"]})
        if "ptsOpen" in entry:
            print(f"{code}: 既に記録済みのためスキップ", file=sys.stderr)
            continue
        soup = fetch_stock_page(code)
        if soup is None:
            print(f"{code}: ページ取得失敗", file=sys.stderr)
            continue
        pts = get_pts_table(soup)
        if not pts or "始値" not in pts:
            print(f"{code}: PTSデータなし", file=sys.stderr)
            continue
        entry["ptsOpen"] = pts["始値"]["price"]
        entry["ptsOpenTime"] = pts["始値"]["time"]
        if "高値" in pts:
            entry["ptsHighEarly"] = pts["高値"]["price"]
            entry["ptsHighEarlyTime"] = pts["高値"]["time"]
        print(f"{code}: {entry}", file=sys.stderr)

    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(day_log)} entries for {today_str}", file=sys.stderr)


if __name__ == "__main__":
    main()
