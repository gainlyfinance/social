"""Morning job: make today's picture and video (with voice) into the data folder.

    python3 autopilot/prepare.py            today (India time)
    POST_DATE=2026-11-01 python3 autopilot/prepare.py
"""
import os
import sys

from common import started, CONFIG, ROOT, item_for, log, media_dir, save_state, state, today

sys.path.insert(0, str(ROOT / 'maker'))
import make  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main():
    if not started():
        log('Autopilot not started yet (config.json start_date). Nothing to do.')
        return 0
    date = today()
    item = item_for(date)
    if not item:
        log('No post planned for', date, '(add it to queue/). Nothing to do.')
        return
    out = media_dir(date)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        make.card(page, item, out / f"{item['slug']}.jpg")
        page.close()
        page = b.new_page()
        make.video(page, item, out / f"{item['slug']}.mp4", os.environ.get('VOICE') or CONFIG['voice'])
        page.close()
        b.close()
    days = state('days')
    days[date] = {**days.get(date, {}), 'slug': item['slug'], 'prepared': True}
    save_state('days', days)
    log('Prepared', date, item['slug'])


if __name__ == '__main__':
    main()
