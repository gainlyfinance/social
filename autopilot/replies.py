"""Every half hour: answers comments that contain a post's keyword (for example "SIP 20") with that post's reply.

Looks at posts from the last `reply_days` days on every platform. Each comment is answered once.
"""
import re
import time
import unicodedata

import platforms as P
from common import started, CONFIG, DRY, log, queue_items, save_state, state
from tokens import threads_token

DEV_DIGITS = str.maketrans('०१२३४५६७८९', '0123456789')
WORDS = {'बीस': '20', 'पच्चीस': '25', 'दस': '10', 'बेटी': 'BETI'}


def norm(text):
    t = unicodedata.normalize('NFKC', text or '').translate(DEV_DIGITS)
    for w, d in WORDS.items():
        t = t.replace(w, d)
    return re.sub(r'[^A-Z0-9]', '', t.upper())


def main():
    if not started():
        log('Autopilot not started yet (config.json start_date). Nothing to do.')
        return 0
    items = {it['slug']: it for it in queue_items()}
    published = state('published', [])
    replied = set(state('replied', []))
    budget = CONFIG.get('max_replies_per_run', 60)
    since = time.time() - CONFIG.get('reply_days', 14) * 86400
    tt = None
    sent = 0
    for post in published:
        if post.get('at', 0) < since or sent >= budget:
            continue
        item = items.get(post['slug'])
        if not item or not item.get('keyword'):
            continue
        key = norm(item['keyword'])
        try:
            if post['platform'] == 'youtube':
                comments = P.youtube_comments(post['id'])
            elif post['platform'] == 'instagram':
                comments = P.instagram_comments(post['id'])
            elif post['platform'] == 'facebook':
                comments = P.facebook_comments(post['id'])
            elif post['platform'] == 'threads':
                tt = tt or threads_token()
                comments = P.threads_comments(tt, post['id'])
            else:
                continue
        except Exception as e:  # noqa: BLE001
            log('Could not read comments on', post['platform'], post['id'], '-', e)
            continue
        for c in comments:
            uid = f"{post['platform']}:{c['id']}"
            if uid in replied or key not in norm(c['text']) or sent >= budget:
                continue
            try:
                if post['platform'] == 'youtube':
                    P.youtube_reply(c['id'], item['reply'])
                elif post['platform'] == 'instagram':
                    P.instagram_reply(c['id'], item['reply'])
                elif post['platform'] == 'facebook':
                    P.facebook_reply(c['id'], item['reply'])
                elif post['platform'] == 'threads':
                    P.threads_post(tt, item['reply'][:490], reply_to=c['id'])
                sent += 1
                if not DRY:
                    replied.add(uid)
                log('Answered', uid)
            except Exception as e:  # noqa: BLE001
                log('Could not answer', uid, '-', e)
    save_state('replied', sorted(replied))
    log('Replies sent:', sent)


if __name__ == '__main__':
    main()
