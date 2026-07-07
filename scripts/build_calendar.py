"""
イチオシ決算の言及履歴(data/ichioshi_history.json)と
マネックス決算スケジュール(data/monex_schedule.json)を証券コードで突き合わせ、
サイト表示用のカレンダーデータ(data/calendar_data.json)を生成する。
"""
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
HISTORY_PATH = DATA_DIR / "ichioshi_history.json"
SCHEDULE_PATH = DATA_DIR / "monex_schedule.json"
OUT_PATH = DATA_DIR / "calendar_data.json"

# 「前回決算」とみなすには、少なくとも何日以上前の言及である必要があるか。
# 決算発表が前倒しになるケースを考慮し、1週間の余裕を持たせる。
# (これより短い間隔の言及は「同じ決算に対する当日掲載」とみなして除外する)
MIN_GAP_DAYS = 7


def parse_date(s: str) -> date:
    return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


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
        target_date = parse_date(entry["date"])

        # 対象日から MIN_GAP_DAYS 日以上前の言及だけを「前回決算」の候補とする
        # (同日や直近の言及は、今回と同じ決算を指しているだけの可能性が高いため除外)
        qualifying = [
            d for d in code_to_dates[code]
            if (target_date - parse_date(d)).days >= MIN_GAP_DAYS
        ]
        if not qualifying:
            continue  # 前回に相当する言及が無いので掲載しない

        key = (entry["date"], code)
        if key in seen:
            continue
        seen.add(key)
        by_date[entry["date"]].append({
            "code": code,
            "name": entry["name"],
            "time": entry["time"],
            "type": entry["type"],
            "lastMentioned": qualifying[0],
            "mentionCount": len(qualifying),
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
