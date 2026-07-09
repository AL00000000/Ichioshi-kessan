"""
毎平日 00:19 JST頃(夜間PTS終了23:59の20分後)に実行。
実行時刻はJSTで日付が変わった直後になるため、対象は「前日」の掲載銘柄。
夜間PTSセッション全体を通じての最終的な高値を記録する。
"""
import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pts_common import fetch_stock_page, get_pts_table, jst_today  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
CALENDAR_PATH = DATA_DIR / "calendar_data.json"
LOG_PATH = DATA_DIR / "pts_detail_log.json"


def main():
    # このジョブはJSTで日付が変わった直後(0:19)に動くので、対象は「前日」
    target = jst_today() - timedelta(days=1)
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
        pts = get_pts_table(soup)
        if not pts or "高値" not in pts:
            print(f"{code}: PTSデータなし", file=sys.stderr)
            continue
        entry["ptsHighFinal"] = pts["高値"]["price"]
        entry["ptsHighFinalTime"] = pts["高値"]["time"]
        print(f"{code}: {entry}", file=sys.stderr)

    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(day_log)} entries for {target_str}", file=sys.stderr)


if __name__ == "__main__":
    main()
