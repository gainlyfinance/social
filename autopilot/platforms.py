"""Posting to YouTube, Instagram, Facebook and Threads, and reading and answering comments.

Every function returns the new post's ID. With DRY_RUN=1 nothing is sent: the call is printed and a fake ID returned.
"""
import json
import os
import pathlib
import time
import urllib.parse

from common import DRY, ApiError, http, log

GRAPH = 'https://graph.facebook.com/v23.0'
THREADS = 'https://graph.threads.net/v1.0'


def env(name):
    v = os.environ.get(name, '').strip()
    if not v:
        raise ApiError(f'secret {name} is missing')
    return v


def dry(what, **info):
    log('DRY RUN, would', what, json.dumps({k: (v if len(str(v)) < 120 else str(v)[:117] + '...') for k, v in info.items()}, ensure_ascii=False))
    return f'dry-{what}-{int(time.time())}'


# ---------------- YouTube ----------------

def yt_token():
    r = http('POST', 'https://oauth2.googleapis.com/token', data={
        'client_id': env('YT_CLIENT_ID'), 'client_secret': env('YT_CLIENT_SECRET'),
        'refresh_token': env('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'})
    return r['access_token']


def youtube_short(path, title, description, tags):
    if DRY:
        return dry('upload YouTube Short', title=title, file=pathlib.Path(path).name)
    tok = yt_token()
    meta = {
        'snippet': {'title': title[:100], 'description': description[:4900], 'tags': [t.lstrip('#') for t in tags][:15],
                    'categoryId': '27', 'defaultLanguage': 'hi', 'defaultAudioLanguage': 'hi'},
        'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False},
    }
    size = pathlib.Path(path).stat().st_size
    start = http('POST', 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
                 json_body=meta, headers={'Authorization': f'Bearer {tok}', 'X-Upload-Content-Type': 'video/mp4',
                                          'X-Upload-Content-Length': str(size)})
    upload_url = start['_headers'].get('Location') or start['_headers'].get('location')
    res = http('PUT', upload_url, raw=pathlib.Path(path).read_bytes(),
               headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'video/mp4'}, timeout=600)
    return res['id']


def youtube_comments(video_id):
    tok = yt_token()
    r = http('GET', 'https://www.googleapis.com/youtube/v3/commentThreads?' + urllib.parse.urlencode(
        {'part': 'snippet', 'videoId': video_id, 'maxResults': 100, 'order': 'time'}), headers={'Authorization': f'Bearer {tok}'})
    out = []
    for t in r.get('items', []):
        top = t['snippet']['topLevelComment']
        out.append({'id': top['id'], 'text': top['snippet'].get('textOriginal', ''),
                    'author': top['snippet'].get('authorChannelId', {}).get('value', '')})
    return out


def youtube_reply(comment_id, text):
    if DRY:
        return dry('reply on YouTube', to=comment_id, text=text)
    tok = yt_token()
    return http('POST', 'https://www.googleapis.com/youtube/v3/comments?part=snippet',
                json_body={'snippet': {'parentId': comment_id, 'textOriginal': text}},
                headers={'Authorization': f'Bearer {tok}'})['id']


# ---------------- Instagram ----------------

def _ig_wait(container, token, minutes=8):
    for _ in range(minutes * 6):
        st = http('GET', f'{GRAPH}/{container}?' + urllib.parse.urlencode({'fields': 'status_code,status', 'access_token': token}))
        code = st.get('status_code')
        if code == 'FINISHED':
            return
        if code in ('ERROR', 'EXPIRED'):
            raise ApiError(f"Instagram could not process the media: {st.get('status')}")
        time.sleep(10)
    raise ApiError('Instagram took too long to process the media')


def _ig_publish(container, token):
    return http('POST', f"{GRAPH}/{env('IG_USER_ID')}/media_publish", data={'creation_id': container, 'access_token': token})['id']


def instagram_reel(video_url, caption, audio_id=None):
    if DRY:
        return dry('post Instagram Reel', video=video_url, caption=caption)
    token, ig = env('META_PAGE_TOKEN'), env('IG_USER_ID')
    data = {'media_type': 'REELS', 'video_url': video_url, 'caption': caption, 'share_to_feed': 'true', 'access_token': token}
    if audio_id:
        data['audio_configuration'] = json.dumps({'audio_id': audio_id, 'audio_volume': 20, 'video_volume': 100})
    c = http('POST', f'{GRAPH}/{ig}/media', data=data)['id']
    _ig_wait(c, token)
    return _ig_publish(c, token)


def instagram_photo(image_url, caption):
    if DRY:
        return dry('post Instagram photo', image=image_url, caption=caption)
    token, ig = env('META_PAGE_TOKEN'), env('IG_USER_ID')
    c = http('POST', f'{GRAPH}/{ig}/media', data={'image_url': image_url, 'caption': caption, 'access_token': token})['id']
    _ig_wait(c, token, minutes=3)
    return _ig_publish(c, token)


def instagram_comments(media_id):
    token = env('META_PAGE_TOKEN')
    r = http('GET', f'{GRAPH}/{media_id}/comments?' + urllib.parse.urlencode({'fields': 'id,text,username', 'limit': 100, 'access_token': token}))
    return [{'id': c['id'], 'text': c.get('text', ''), 'author': c.get('username', '')} for c in r.get('data', [])]


def instagram_reply(comment_id, text):
    if DRY:
        return dry('reply on Instagram', to=comment_id, text=text)
    return http('POST', f'{GRAPH}/{comment_id}/replies', data={'message': text, 'access_token': env('META_PAGE_TOKEN')})['id']


# ---------------- Facebook Page ----------------

def facebook_reel(video_url, description):
    if DRY:
        return dry('post Facebook Reel', video=video_url, text=description)
    token, page = env('META_PAGE_TOKEN'), env('FB_PAGE_ID')
    s = http('POST', f'{GRAPH}/{page}/video_reels', data={'upload_phase': 'start', 'access_token': token})
    http('POST', s['upload_url'], headers={'Authorization': f'OAuth {token}', 'file_url': video_url})
    http('POST', f'{GRAPH}/{page}/video_reels', data={'upload_phase': 'finish', 'video_id': s['video_id'],
                                                      'video_state': 'PUBLISHED', 'description': description, 'access_token': token})
    return s['video_id']


def facebook_photo(image_url, caption):
    if DRY:
        return dry('post Facebook photo', image=image_url, text=caption)
    r = http('POST', f"{GRAPH}/{env('FB_PAGE_ID')}/photos", data={'url': image_url, 'caption': caption, 'access_token': env('META_PAGE_TOKEN')})
    return r['id']


def facebook_comments(object_id):
    token, page = env('META_PAGE_TOKEN'), env('FB_PAGE_ID')
    r = http('GET', f'{GRAPH}/{object_id}/comments?' + urllib.parse.urlencode({'fields': 'id,message,from', 'limit': 100, 'access_token': token}))
    return [{'id': c['id'], 'text': c.get('message', ''), 'author': (c.get('from') or {}).get('id', '')}
            for c in r.get('data', []) if (c.get('from') or {}).get('id') != page]


def facebook_reply(comment_id, text):
    if DRY:
        return dry('reply on Facebook', to=comment_id, text=text)
    return http('POST', f'{GRAPH}/{comment_id}/comments', data={'message': text, 'access_token': env('META_PAGE_TOKEN')})['id']


# ---------------- Threads ----------------

def _threads_publish(container, token, uid):
    for _ in range(36):
        st = http('GET', f'{THREADS}/{container}?' + urllib.parse.urlencode({'fields': 'status,error_message', 'access_token': token}))
        if st.get('status') == 'FINISHED':
            break
        if st.get('status') in ('ERROR', 'EXPIRED'):
            raise ApiError(f"Threads could not process the media: {st.get('error_message')}")
        time.sleep(10)
    return http('POST', f'{THREADS}/{uid}/threads_publish', data={'creation_id': container, 'access_token': token})['id']


def threads_post(token, text, image_url=None, video_url=None, reply_to=None):
    if DRY:
        return dry('post on Threads', text=text, image=image_url, video=video_url, reply_to=reply_to)
    uid = env('THREADS_USER_ID')
    data = {'text': text, 'access_token': token}
    if video_url:
        data.update(media_type='VIDEO', video_url=video_url)
    elif image_url:
        data.update(media_type='IMAGE', image_url=image_url)
    else:
        data.update(media_type='TEXT')
    if reply_to:
        data['reply_to_id'] = reply_to
    c = http('POST', f'{THREADS}/{uid}/threads', data=data)['id']
    return _threads_publish(c, token, uid)


def threads_comments(token, media_id):
    r = http('GET', f'{THREADS}/{media_id}/replies?' + urllib.parse.urlencode({'fields': 'id,text,username', 'access_token': token}))
    me = os.environ.get('THREADS_USERNAME', '')
    return [{'id': c['id'], 'text': c.get('text', ''), 'author': c.get('username', '')} for c in r.get('data', []) if c.get('username') != me]


def threads_refresh(token):
    r = http('GET', 'https://graph.threads.net/refresh_access_token?' + urllib.parse.urlencode({'grant_type': 'th_refresh_token', 'access_token': token}))
    return r['access_token'], int(r.get('expires_in', 0))
