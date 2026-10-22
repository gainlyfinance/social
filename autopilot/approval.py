"""Approve mode: every evening a GitHub issue shows tomorrow's video and picture to the owner. Writing "stop" in a
comment (or adding the label "stop") keeps the day's posts from going out.

    python3 autopilot/approval.py open      after the media is online
    python3 autopilot/approval.py queue     warns the owner when fewer than 5 days of posts are left in queue/
"""
import datetime as dt
import sys

from common import CONFIG, gh, item_for, log, media_url, prepare_date, queue_items, save_state, state, wait_until_online

QUEUE_WARN_DAYS = 5


def open_issue():
    date = prepare_date()
    item = item_for(date)
    days = state('days')
    if not item or not days.get(date, {}).get('prepared'):
        log('Nothing prepared for', date)
        return
    video = media_url(date, f"{item['slug']}.mp4")
    photo = media_url(date, f"{item['slug']}.jpg")
    wait_until_online(video)
    wait_until_online(photo)
    if days[date].get('issue'):
        log('Issue already open:', days[date]['issue'])
        return
    mode = CONFIG.get('mode', 'approve')
    body = (f"@{CONFIG['owner_github']} कल की पोस्ट ({date})\n\n"
            f"**{item['title']}**\n\n"
            f"- वीडियो: {video}\n- फोटो: {photo}\n\n"
            f"**कीवर्ड:** `{item['keyword']}`\n\n**जवाब (कमेंट करने वालों को):**\n> {item['reply']}\n\n"
            f"**कैप्शन:**\n> {item['caption']}\n\n"
            + (f"वीडियो {date} को सुबह 6 बजे और फोटो शाम 7 बजे जाएंगे। रोकना हो तो उससे पहले यहां कमेंट में `stop` लिखें।"
               if mode == 'approve' else 'Auto mode: posts go out on time.'))
    issue = gh('POST', '/issues', {'title': f'{date}: {item["title"]}', 'body': body, 'labels': ['today']})
    # Locked: only the owner and collaborators can comment, so nobody else can write "stop" or spam it.
    gh('PUT', f"/issues/{issue['number']}/lock", {'lock_reason': 'off-topic'})
    days[date]['issue'] = issue['number']
    save_state('days', days)
    log('Opened issue', issue['number'])


def stopped(date):
    """True when the owner said stop for this day."""
    if CONFIG.get('mode', 'approve') != 'approve':
        return False
    n = state('days').get(date, {}).get('issue')
    if not n:
        return False
    issue = gh('GET', f'/issues/{n}')
    if any(lbl['name'].lower() == 'stop' for lbl in issue.get('labels', [])):
        return True
    comments = gh('GET', f'/issues/{n}/comments?per_page=100')
    allowed = {'OWNER', 'COLLABORATOR', 'MEMBER'}
    return any(c.get('author_association') in allowed and 'stop' in c.get('body', '').lower()
               for c in (comments if isinstance(comments, list) else []))


def note(date, text, close=False):
    n = state('days').get(date, {}).get('issue')
    if not n:
        return
    gh('POST', f'/issues/{n}/comments', {'body': text})
    if close:
        gh('PATCH', f'/issues/{n}', {'state': 'closed'})


def days_left():
    """How many days in a row after the day being prepared already have a post in queue/."""
    have = {it['date'] for it in queue_items()}
    d, n = dt.date.fromisoformat(prepare_date()), 0
    while (d + dt.timedelta(days=n + 1)).isoformat() in have:
        n += 1
    return n


def queue_warning():
    """Opens one locked issue (GitHub emails the owner) when the queue is running out. Closes it again once
    the queue has been filled."""
    left = days_left()
    open_ = gh('GET', '/issues?state=open&labels=queue&per_page=10')
    open_ = open_ if isinstance(open_, list) else []
    if left >= QUEUE_WARN_DAYS:
        for i in open_:
            gh('POST', f"/issues/{i['number']}/comments", {'body': f'Queue भर गई, अब {left} दिन की पोस्ट तैयार हैं।'})
            gh('PATCH', f"/issues/{i['number']}", {'state': 'closed'})
        log('Queue OK:', left, 'days left')
        return
    if open_:
        log('Queue low,', left, 'days left, issue already open:', open_[0]['number'])
        return
    last = (dt.date.fromisoformat(prepare_date()) + dt.timedelta(days=left)).isoformat()
    body = (f"@{CONFIG['owner_github']} Queue में सिर्फ **{left} दिन** की पोस्ट बची हैं (आखिरी: {last})।\n\n"
            f"उसके बाद कुछ पोस्ट नहीं होगा। Claude से अगले महीने की queue बनवा लें "
            f"(`queue/YYYY-MM.json`)। Queue भरते ही ये issue अपने आप बंद हो जाएगा।")
    issue = gh('POST', '/issues', {'title': f'Queue खत्म होने वाली है: {left} दिन बचे', 'body': body, 'labels': ['queue']})
    gh('PUT', f"/issues/{issue['number']}/lock", {'lock_reason': 'off-topic'})
    log('Queue low, opened issue', issue['number'])


if __name__ == '__main__':
    if sys.argv[1:] == ['open']:
        open_issue()
    elif sys.argv[1:] == ['queue']:
        queue_warning()
