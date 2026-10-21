"""Approve mode: every evening a GitHub issue shows tomorrow's video and picture to the owner. Writing "stop" in a
comment (or adding the label "stop") keeps the day's posts from going out.

    python3 autopilot/approval.py open      after the media is online
"""
import sys

from common import CONFIG, gh, item_for, log, media_url, prepare_date, save_state, state, wait_until_online


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


if __name__ == '__main__':
    if sys.argv[1:] == ['open']:
        open_issue()
