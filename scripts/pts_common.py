"""
夜間PTS・場中株価のスナップショット取得で共通利用するヘルパー。
株探の個別銘柄ページ(ログイン不要)から、時刻付きのPTS/場中OHLCテーブルをパースする。
"""
import re
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

JST = timezone(timedelta(hours=9))


def jst_today() -> date:
    """実行環境のタイムゾーンに関わらず、JST基準の「今日」を返す。
    GitHub ActionsのランナーはUTCで動くため、date.today()を直接使うと
    日付が変わる境界付近でずれる(特にJST 0時台に実行するジョブで問題になる)。"""
    return datetime.now(JST).date()


def prev_business_day(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:  # 土日はスキップ(祝日は考慮しない)
        d -= timedelta(days=1)
    return d


def _parse_row(tr):
    th = tr.find("th")
    tds = tr.find_all("td")
    if not th or not tds:
        return None
    label = th.get_text(strip=True)
    price_text = tds[0].get_text(strip=True).replace(",", "")
    try:
        price = float(price_text)
    except ValueError:
        return None
    time_tag = tr.find("time")
    time_text = None
    if time_tag:
        time_text = time_tag.get_text(strip=True)
    return label, price, time_text


def fetch_stock_page(code: str):
    url = f"https://kabutan.jp/stock/?code={code}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    r.encoding = "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def get_pts_table(soup):
    """夜間PTSの 始値/高値/安値/現在値 (それぞれ時刻付き) を返す。"""
    div = soup.find("div", class_="stock_pts_div")
    if div is None:
        return None
    table = div.find("table")
    if table is None:
        return None
    result = {}
    for tr in table.find_all("tr"):
        parsed = _parse_row(tr)
        if parsed:
            label, price, time_text = parsed
            result[label] = {"price": price, "time": time_text}
    return result or None


def get_today_session_table(soup):
    """本日の場中 始値/高値/安値/終値 (それぞれ時刻付き) を返す。"""
    left = soup.find("div", id="kobetsu_left")
    if left is None:
        return None
    h2 = left.find("h2")
    if h2 is None:
        return None
    table = h2.find_next("table")
    if table is None:
        return None
    result = {}
    for tr in table.find_all("tr"):
        parsed = _parse_row(tr)
        if parsed:
            label, price, time_text = parsed
            result[label] = {"price": price, "time": time_text}
    return result or None
