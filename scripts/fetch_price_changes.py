"""
calendar_data.json の各掲載銘柄について、株価関連の指標を追記する。

1. 前回イチオシ決算掲載日の株価騰落率(lastMentionedPriceChange)
   判定ルール:
     - 決算発表時刻が場中(9:00〜15:00未満)の場合 -> 発表当日の騰落率
     - それ以外(寄り付き前 or 引け後)の場合      -> 発表翌営業日の騰落率
     (発表時刻は同じ銘柄の直近スケジュール時刻を代用する。決算発表は毎回同じ時間帯に
      行われることが多いため、次回の予定時刻を過去の発表タイミングの目安として使う)

2. 決算発表前5営業日の値動き(preEarningsChange)
   その決算発表日から5営業日前の終値 -> 発表日当日の終値(決算はほとんど引け後発表
   のため、当日終値を「発表直前の株価」とみなす)までの騰落率。

株価データは株探の時系列株価ページ(ログイン不要)から取得する。
"""
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
CALENDAR_PATH = DATA_DIR / "calendar_data.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_price_cache: dict[str, list[tuple[str, float, float]]] = {}


def fetch_price_rows(code: str, max_pages: int = 5) -> list[tuple[str, float, float]]:
    """(YYYYMMDD, 終値, 前日比%) のリストを新しい順で返す。ページをまたいで蓄積・キャッシュする。"""
    if code in _price_cache:
        return _price_cache[code]
    rows: list[tuple[str, float, float]] = []
    for page in range(1, max_pages + 1):
        url = f"https://kabutan.jp/stock/kabuka?code={code}&ashi=day&page={page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException:
            break
        if r.status_code != 200:
            break
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        found_this_page = 0
        for tr in soup.select("tr"):
            th = tr.find("th")
            time_tag = th.find("time") if th else None
            if not time_tag or not time_tag.get("datetime"):
                continue
            tds = tr.find_all("td")
            if len(tds) < 6:
                continue
            close_text = tds[3].get_text(strip=True).replace(",", "")
            pct_text = tds[5].get_text(strip=True).replace("+", "").replace("%", "")
            try:
                close = float(close_text)
                pct = float(pct_text)
            except ValueError:
                continue
            dstr = time_tag["datetime"].replace("-", "")
            rows.append((dstr, close, pct))
            found_this_page += 1
        if found_this_page == 0:
            break
    _price_cache[code] = rows
    return rows


def is_intraday(time_text: str) -> bool:
    m = re.search(r"(\d{1,2}):(\d{2})", time_text)
    if not m:
        return False
    minutes = int(m.group(1)) * 60 + int(m.group(2))
    # 大引け(15:00)ちょうど・それ以降は「引け後」扱いとする
    return 9 * 60 <= minutes < 15 * 60


def get_price_change(code: str, mention_date: str, time_text: str):
    rows = fetch_price_rows(code)
    if not rows:
        return None
    dates = [d for d, _, _ in rows]
    if mention_date not in dates:
        return None
    idx = dates.index(mention_date)
    if is_intraday(time_text):
        return {"pct": rows[idx][2], "type": "同日"}
    # 翌営業日 = リストの1つ前(新しい順なので idx-1)
    if idx == 0:
        return None  # まだ翌営業日のデータが無い
    return {"pct": rows[idx - 1][2], "type": "翌営業日"}


def get_pre_earnings_momentum(code: str, earnings_date: str, lookback_days: int = 5):
    """決算発表日の lookback_days 営業日前の終値 -> 発表日当日終値 までの騰落率。"""
    rows = fetch_price_rows(code)
    if not rows:
        return None
    dates = [d for d, _, _ in rows]
    if earnings_date not in dates:
        return None  # まだ発表日を迎えていない(株価データが無い)
    idx_d = dates.index(earnings_date)
    idx_before = idx_d + lookback_days
    if idx_before >= len(rows):
        return None  # 遡れる日数が足りない
    close_d = rows[idx_d][1]
    close_before = rows[idx_before][1]
    if not close_before:
        return None
    pct = round((close_d - close_before) / close_before * 100, 2)
    return {"pct": pct, "fromDate": rows[idx_before][0]}


def main():
    data = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    total = 0
    filled = 0
    filled_pre = 0
    for date_str, items in data["days"].items():
        for item in items:
            total += 1
            change = get_price_change(item["code"], item["lastMentioned"], item["time"])
            if change:
                item["lastMentionedPriceChange"] = change["pct"]
                item["lastMentionedPriceChangeType"] = change["type"]
                filled += 1

            momentum = get_pre_earnings_momentum(item["code"], date_str)
            if momentum:
                item["preEarningsChange"] = momentum["pct"]
                item["preEarningsFromDate"] = momentum["fromDate"]
                filled_pre += 1

            print(f"{item['code']} {date_str}: lastMention={change} preEarnings={momentum}", file=sys.stderr)

    CALENDAR_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"lastMention filled {filled}/{total}, preEarnings filled {filled_pre}/{total}", file=sys.stderr)


if __name__ == "__main__":
    main()
