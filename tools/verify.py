"""Checks that every key in GitHub Secrets works, without posting anything. Run by the "Check keys" workflow.

Prints one line per service: OK and the account name, or what is wrong. Never prints a key.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GRAPH = 'https://graph.facebook.com/v23.0'


def get(url, data=None, headers=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode())
            msg = msg.get('error', msg)
            if isinstance(msg, dict):
                msg = msg.get('message') or msg.get('error_description') or msg.get('status') or str(msg)
        except Exception:
            msg = str(e)
        raise RuntimeError(f'{e.code}: {msg}') from None


def env(name):
    v = os.environ.get(name, '').strip()
    if not v:
        raise RuntimeError(f'secret {name} is empty or missing')
    return v


def facebook():
    page = get(f"{GRAPH}/{env('FB_PAGE_ID')}?" + urllib.parse.urlencode({'fields': 'name', 'access_token': env('META_PAGE_TOKEN')}))
    return f"Facebook Page: {page['name']}"


def instagram():
    ig = get(f"{GRAPH}/{env('IG_USER_ID')}?" + urllib.parse.urlencode({'fields': 'username', 'access_token': env('META_PAGE_TOKEN')}))
    return f"Instagram: @{ig['username']}"


def threads():
    me = get('https://graph.threads.net/v1.0/me?' + urllib.parse.urlencode({'fields': 'id,username', 'access_token': env('THREADS_TOKEN')}))
    note = '' if me['id'] == env('THREADS_USER_ID') else ' (THREADS_USER_ID does not match this token)'
    return f"Threads: @{me['username']}{note}"


def youtube():
    tok = get('https://oauth2.googleapis.com/token', {
        'client_id': env('YT_CLIENT_ID'), 'client_secret': env('YT_CLIENT_SECRET'),
        'refresh_token': env('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'})
    ch = get('https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true',
             headers={'Authorization': 'Bearer ' + tok['access_token']}).get('items', [])
    return 'YouTube: ' + (ch[0]['snippet']['title'] if ch else '(no channel on this account)')


def tts():
    v = get('https://texttospeech.googleapis.com/v1/voices?' + urllib.parse.urlencode({'languageCode': 'hi-IN', 'key': env('GOOGLE_TTS_KEY')}))
    names = sorted(x['name'] for x in v.get('voices', []))
    return f'Google Text-to-Speech: {len(names)} Hindi voices'


def main():
    failed = 0
    for check in (facebook, instagram, threads, youtube, tts):
        try:
            print('OK    ', check())
        except Exception as e:  # noqa: BLE001
            failed += 1
            print('FAIL  ', check.__name__, '-', e)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
