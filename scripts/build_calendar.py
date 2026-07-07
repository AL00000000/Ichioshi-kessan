"""
イチオシ決算の言及履歴(data/ichioshi_history.json)と
マネックス決算スケジュール(data/monex_schedule.json)を証券コードで突き合わせ、
サイト表示用のカレンダーデータ(data/calendar_data.json)を生成する。
"""
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
HISTORY_PATH = DATA_DIR / "ichioshi_history.json"
SCHEDULE_PATH = DATA_DIR / "monex_schedule.json"
OUT_PATH = DATA_DIR / "calendar_data.json"


def load_history():
    """イチオシ決算履歴を読み込み、証券コード -> 言及日リスト の辞書を返す"""
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    code_to_dates = defaultdict(list)
    for entry in history:
        for code in entry["codes"]:
            code_to_dates[code].append(entry["date"])
    for code in code_to_dates:
        code_to_dates[code].sort(reverse=True)
    return code_to_dates


def build():
    code_to_dates = load_history()
    schedule = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))

    by_date = defaultdict(list)
    seen = set()
    for entry in schedule:
        code = entry["code"]
        if code not in code_to_dates:
            continue
        key = (entry["date"], code)
        if key in seen:
            continue
        seen.add(key)
        by_date[entry["date"]].append({
            "code": code,
            "name": entry["name"],
            "time": entry["time"],
            "type": entry["type"],
            "lastMentioned": code_to_dates[code][0],
            "mentionCount": len(code_to_dates[code]),
        })

    result = {
        "generatedFrom": {
            "historyEntries": len(json.loads(HISTORY_PATH.read_text(encoding="utf-8"))),
            "watchlistCodes": len(code_to_dates),
            "scheduleEntries": len(schedule),
        },
        "days": {d: sorted(v, key=lambda x: x["code"]) for d, v in sorted(by_date.items())},
    }
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"watchlist codes: {len(code_to_dates)}")
    print(f"matched days: {len(by_date)}")
    print(f"total matches: {sum(len(v) for v in by_date.values())}")
    print(f"saved to {OUT_PATH}")


if __name__ == "__main__":
    build()
