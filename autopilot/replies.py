"""Every half hour: answers comments that contain a post's keyword (for example "SIP 20") with that post's reply.

Looks at posts from the last `reply_days` days on every platform. Each comment is answered once.
"""
import re
import time
import unicodedata

import platforms as P
from common import CONFIG, DRY, log, queue_items, save_state, state
from tokens import threads_token

DEV_DIGITS = str.maketrans('०१२३४५६७८९', '0123456789')
# Hindi words people may type instead of the keyword's Latin letters or digits (longer words first).
WORDS = {'पच्चीस': '25', 'पैंतीस': '35', 'पंद्रह': '15', 'अठारह': '18', 'चालीस': '40', 'सत्तर': '70', 'तीस': '30',
         'बीस': '20', 'पांच': '5', 'पाँच': '5', 'दस': '10', 'सात': '7', 'चार': '4', 'बेटी': 'BETI', 'लोन': 'LOAN',
         'होम': 'HOME', 'टैक्स': 'TAX', 'गोल्ड': 'GOLD', 'सोना': 'GOLD', 'चेन': 'CHAIN', 'चैन': 'CHAIN', 'महंगाई': 'MEHNGAI', 'खर्च': 'KHARCH',
         'फीस': 'FEES', 'करोड़': 'CRORE', 'ब्याज': 'BYAJ', 'लम्प': 'LUMP'}


def norm(text):
    t = unicodedata.normalize('NFKC', text or '').translate(DEV_DIGITS)
    for w, d in WORDS.items():
        t = t.replace(w, d)
    return re.sub(r'[^A-Z0-9]', '', t.upper())


def main():
    # Replies run whenever something has been posted, even before start_date (for test posts).
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
