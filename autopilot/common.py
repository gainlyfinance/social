"""Shared helpers for the daily jobs: config, queue, the data folder (media + state), HTTP, GitHub issues."""
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = pathlib.Path(os.environ.get('DATA_DIR', ROOT / 'data'))     # checkout of the "data" branch
CONFIG = json.loads((ROOT / 'config.json').read_text())
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DRY = os.environ.get('DRY_RUN', '').lower() in ('1', 'true', 'yes')


def today():
    return os.environ.get('POST_DATE') or dt.datetime.now(IST).date().isoformat()


def prepare_date():
    """The evening job prepares tomorrow's post (India time), so the owner can see it the night before."""
    return os.environ.get('POST_DATE') or (dt.datetime.now(IST).date() + dt.timedelta(days=1)).isoformat()


def started(date=None):
    """Scheduled runs do nothing until config.json has a start_date on or before the post's date (manual runs with
    a date or a dry run always go ahead)."""
    if os.environ.get('POST_DATE') or DRY:
        return True
    start = CONFIG.get('start_date') or ''
    return bool(start) and start <= (date or today())


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ---------- queue ----------

def queue_items():
    items = []
    for f in sorted((ROOT / 'queue').glob('20*.json')):
        items += json.loads(f.read_text())
    return items


def item_for(date):
    for it in queue_items():
        if it.get('date') == date:
            return it
    return None


# ---------- state in the data branch ----------

def state(name, default=None):
    p = DATA / 'state' / f'{name}.json'
    return json.loads(p.read_text()) if p.exists() else (default if default is not None else {})


def save_state(name, value):
    p = DATA / 'state' / f'{name}.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')


def media_dir(date):
    d = DATA / 'media' / date
    d.mkdir(parents=True, exist_ok=True)
    return d


def media_url(date, name):
    return f"{CONFIG['media_base_url'].rstrip('/')}/media/{date}/{urllib.parse.quote(name)}"


# ---------- HTTP ----------

class ApiError(RuntimeError):
    pass


def http(method, url, data=None, json_body=None, headers=None, raw=None, timeout=120):
    headers = dict(headers or {})
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode()
        headers['Content-Type'] = 'application/json'
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
    elif raw is not None:
        body = raw
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode() or '{}'
            out = json.loads(text) if text.strip().startswith(('{', '[')) else {'_text': text}
            out_headers = dict(r.headers)
            if isinstance(out, dict):
                out['_headers'] = out_headers
            return out
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors='replace')[:600]
        # Never echo tokens: strip query strings from the URL in errors.
        raise ApiError(f'{method} {url.split("?")[0]} -> {e.code}: {detail}') from None


def wait_until_online(url, tries=40, pause=15):
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(pause)
    raise ApiError(f'media not online yet: {url}')


# ---------- GitHub (approval issues) ----------

def gh(method, path, body=None):
    repo, token = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_TOKEN']
    return http(method, f'https://api.github.com/repos/{repo}{path}', json_body=body,
                headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'})


def caption_for(item, platform):
    """Caption with hashtags and the calculator link where links work."""
    link = f"https://gainly.in/hi/{item['calculator']}"
    tags = ' '.join(item.get('hashtags', []))
    text = item['caption']
    if platform == 'threads':
        return (text[: 440] + ' ' + (item.get('hashtags') or ['#Gainly'])[0]).strip()
    if platform == 'facebook':
        return f'{text}\n\n{link}\n\n{tags}'
    if platform == 'youtube':
        return f"{text}\n\nफ्री कैलकुलेटर: {link}\n\n{tags} #Shorts"
    return f'{text}\n\n{tags}'
