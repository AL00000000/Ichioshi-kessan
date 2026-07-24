"""
マネックス証券「国内株式決算カレンダー」から、指定期間内の決算発表予定を取得する。
ログイン不要。カレンダーの日付セルを実際にクリックし、表示された結果テーブルをパースする。
1日ずつしかクエリできない仕様のため、日付セルを順にクリックして巡回する。

注意: このサイトはヘッドレスChromiumを403でブロックする(ボット判定)。
      headless=False (仮想ディスプレイ上でも可)で実行すること。
      カレンダーは「当月+翌月」の2ヶ月分しか表示されないため、取得範囲もその範囲に限られる。
"""
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

BASE_URL = "https://mst.monex.co.jp/mst/servlet/ITS/fi/FIClosingCalendarJPGuest"
OUT_PATH = Path(__file__).parent.parent / "docs" / "data" / "monex_schedule.json"


def get_sys_date(page: Page) -> date:
    val = page.locator("#stdDate").get_attribute("value")
    return date(int(val[0:4]), int(val[4:6]), int(val[6:8]))


def click_day_and_scrape(page: Page, target: date, table_index: int) -> list[dict] | None:
    tables = page.locator("table.cal-day")
    if table_index >= tables.count():
        return None
    table = tables.nth(table_index)
    cells = table.locator(".has-count")
    n = cells.count()
    found = None
    for i in range(n):
        cell = cells.nth(i)
        text = cell.inner_text().strip()
        m = re.match(r"^(\d{1,2})", text)
        if m and int(m.group(1)) == target.day:
            found = cell
            break
    if found is None:
        return []  # その日は発表なし

    found.click()
    page.wait_for_timeout(900)

    result_table = None
    for t in page.locator("table").all():
        txt = t.inner_text()
        if "発表日" in txt[:80] and "銘柄コード" in txt:
            result_table = t
            break
    if result_table is None:
        return []

    trs = result_table.locator("tr")
    n_rows = trs.count()
    results = []
    for i in range(1, n_rows):
        tds = trs.nth(i).locator("td")
        if tds.count() < 4:
            continue
        cell_texts = [tds.nth(j).inner_text().strip() for j in range(tds.count())]
        full = " ".join(cell_texts)
        code_m = re.search(r"[（(]([0-9]{3,4}[A-Za-z]?)[）)]", full)
        if not code_m:
            continue
        name_m = re.split(r"[（(][0-9]{3,4}[A-Za-z]?[）)]", cell_texts[2])[0].strip() if len(cell_texts) > 2 else ""
        results.append({
            "date": target.strftime("%Y%m%d"),
            "time": cell_texts[1] if len(cell_texts) > 1 else "",
            "name": name_m,
            "code": code_m.group(1),
            "type": cell_texts[3] if len(cell_texts) > 3 else "",
        })
    return results


def scrape_upcoming(days: int = 45, lookback_days: int = 20):
    """今後days日分に加え、直近lookback_days日分も再取得する。
    直近分は「予定」から「実績」(確定時刻)に更新されていることが多く、
    build_calendar.py側でこの最新時刻に上書きされる。
    (カレンダーが当月+翌月しか表示しないため、当月の範囲を超えるlookbackは
    自動的にスキップされる)
    """
    all_results = []
    with sync_playwright() as p:
        # このサイトはヘッドレスブラウザを403でブロックするため、ヘッド付きモードで起動する
        # (CI環境ではxvfb-run等の仮想ディスプレイ上で実行する)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1920, "height": 1000})
        page.goto(BASE_URL)
        page.wait_for_timeout(1500)

        # 1ページの表示件数を100件に増やしておく(デフォルト20件だと当日発表が多い日に取りこぼす)
        hundred_link = page.locator("a", has_text="100件").first
        if hundred_link.count() > 0:
            hundred_link.click()
            page.wait_for_timeout(1200)

        sys_date = get_sys_date(page)
        start = sys_date - timedelta(days=lookback_days)
        end = sys_date + timedelta(days=days)

        d = start
        while d <= end:
            if d.weekday() < 5:  # 平日のみ
                month_offset = (d.year - sys_date.year) * 12 + (d.month - sys_date.month)
                if month_offset < 0 or month_offset > 1:
                    print(f"{d}: 表示範囲外(当月+翌月のみ対応)のためスキップ", file=sys.stderr)
                    d += timedelta(days=1)
                    continue
                res = click_day_and_scrape(page, d, month_offset)
                if res:
                    print(f"{d}: {len(res)}件", file=sys.stderr)
                    all_results.extend(res)
            d += timedelta(days=1)

        browser.close()
    return all_results


if __name__ == "__main__":
    n_days = int(sys.argv[1]) if len(sys.argv) > 1 else 45
    data = scrape_upcoming(n_days)
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(data)} entries to {OUT_PATH}", file=sys.stderr)
