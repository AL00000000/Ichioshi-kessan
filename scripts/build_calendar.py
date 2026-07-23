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


EXTRA_FIELDS = (
    "lastMentionedPriceChange", "lastMentionedPriceChangeType",
    "referenceClose", "preEarningsChange", "preEarningsFromDate",
)


def load_existing_days():
    """既存のcalendar_data.jsonを (date, code) -> item の辞書として読み込む。
    マネックスの取得窓(直近45日)から外れた過去日を保持するためと、
    fetch_price_changes.py等が後から追記した株価系フィールドを
    再生成時に消さないようにするために使う。"""
    if not OUT_PATH.exists():
        return {}, {}
    old = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    by_key = {}
    by_day = old.get("days", {})
    for d, items in by_day.items():
        for it in items:
            by_key[(d, it["code"])] = it
    return by_key, by_day


def build():
    code_to_dates = load_history()
    schedule = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    existing_by_key, existing_by_day = load_existing_days()

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
        item = {
            "code": code,
            "name": entry["name"],
            "time": entry["time"],
            "type": entry["type"],
            "lastMentioned": qualifying[0],
            "mentionCount": len(qualifying),
        }
        # 既に株価系データが取得済みなら引き継ぐ(再生成のたびに消さない)
        old_item = existing_by_key.get(key)
        if old_item:
            for f in EXTRA_FIELDS:
                if f in old_item:
                    item[f] = old_item[f]
        by_date[entry["date"]].append(item)

    # 今回のマネックス取得窓に無かった過去日は、既存データをそのまま保持する
    fresh_dates = set(by_date.keys())
    for d, items in existing_by_day.items():
        if d not in fresh_dates:
            by_date[d] = items

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
