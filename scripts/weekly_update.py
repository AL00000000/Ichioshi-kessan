"""
週次自動更新のエントリポイント。
1. 直近のイチオシ決算記事を取得(ログイン不要・無料枠のみ)
2. マネックス決算カレンダーから今後の発表予定を取得
3. 突き合わせてカレンダー用データを再生成
4. 各掲載銘柄の前回イチオシ決算掲載日の株価騰落率を追記
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def run(script_name, args=None):
    cmd = [sys.executable, str(SCRIPTS_DIR / script_name)] + (args or [])
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    run("fetch_recent_ichioshi.py")
    run("monex_scraper.py", ["45"])
    run("build_calendar.py")
    run("fetch_price_changes.py")
