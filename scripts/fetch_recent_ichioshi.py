"""
直近のイチオシ決算記事を取得し、docs/data/ichioshi_history.json に追記する。
直近(約30日以内)は無料で閲覧できるため、ログイン不要・requestsのみで完結する。
週次で実行する想定(直近10日分を見れば取りこぼしなく追いつける)。
"""
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HISTORY_PATH = Path(__file__).parent.parent / "docs" / "data" / "ichioshi_history.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
LOOKBACK_DAYS = 10


def fetch_day(d: date):
    dstr = d.strftime("%Y%m%d")
    url = f"https://kabutan.jp/news/marketnews/?category=9&date={dstr}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    target = None
    for a in soup.select("a[href*='b=n']"):
        row = a.find_parent("tr")
        if row and "イチオシ決算" in a.get_text() and row.find("time"):
            target = a
            break
    if target is None:
        return None
    article_id = target["href"].split("=n")[1]
    art_url = f"https://kabutan.jp/news/marketnews/?b=n{article_id}"
    r2 = requests.get(art_url, headers=HEADERS, timeout=15)
    r2.encoding = "utf-8"
    art_soup = BeautifulSoup(r2.text, "html.parser")
    article = art_soup.find("article") or art_soup.body
    text = article.get_text()
    cut_idx = text.find("の決算発表銘柄（予定）")
    main_text = text[:cut_idx] if cut_idx > -1 else text
    codes = sorted(set(re.findall(r"<([0-9]{3,4}[A-Za-z]?)>", main_text)))
    return {"date": dstr, "articleId": article_id, "codes": codes}


def main():
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8")) if HISTORY_PATH.exists() else []
    existing_dates = {e["date"] for e in history}

    today = date.today()
    added = 0
    for i in range(LOOKBACK_DAYS):
        d = today - timedelta(days=i)
        dstr = d.strftime("%Y%m%d")
        if dstr in existing_dates:
            continue
        entry = fetch_day(d)
        if entry:
            history.append(entry)
            added += 1
            print(f"{dstr}: 追加 ({len(entry['codes'])}銘柄)", file=sys.stderr)

    history.sort(key=lambda e: e["date"], reverse=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"added {added} new entries, total {len(history)}", file=sys.stderr)


if __name__ == "__main__":
    main()
