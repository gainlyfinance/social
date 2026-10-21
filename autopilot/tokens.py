"""The Threads token lasts 60 days. It is renewed every week and kept, encrypted with THREADS_APP_SECRET, in the
data branch (state/threads_token.enc). The THREADS_TOKEN secret is only the starting point."""
import base64
import hashlib
import os
import time

from cryptography.fernet import Fernet, InvalidToken

from common import DATA, DRY, log, state, save_state
from platforms import threads_refresh


def _box():
    key = hashlib.sha256(os.environ['THREADS_APP_SECRET'].encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def threads_token():
    p = DATA / 'state' / 'threads_token.enc'
    token = None
    if p.exists():
        try:
            token = _box().decrypt(p.read_bytes()).decode()
        except InvalidToken:
            log('Stored Threads token could not be read, using the THREADS_TOKEN secret')
    token = token or os.environ['THREADS_TOKEN'].strip()
    info = state('threads_token_info', {})
    if not DRY and time.time() - info.get('refreshed', 0) > 7 * 86400:
        try:
            token, expires = threads_refresh(token)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(_box().encrypt(token.encode()))
            save_state('threads_token_info', {'refreshed': int(time.time()), 'expires_in_days': expires // 86400})
            log('Threads token renewed, valid for', expires // 86400, 'days')
        except Exception as e:  # noqa: BLE001
            log('Threads token not renewed this time:', e)
    return token
