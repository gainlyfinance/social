"""Get the YouTube permission (refresh token) for the Gainly channel. Run it on your own computer:

    python3 tools/youtube_token.py

It asks for the OAuth client ID and secret (Google Cloud > Google Auth Platform > Clients, type "Desktop app"),
opens Google's "allow" page in your browser, catches the answer on this computer (127.0.0.1) and prints the
refresh token and the channel it belongs to. Put them in GitHub > Settings > Secrets > Actions as
YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN. Nothing is saved or sent anywhere except to Google.
"""
import getpass
import http.server
import json
import secrets
import urllib.parse
import urllib.request
import webbrowser

SCOPES = 'https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl'


def main():
    client_id = input('OAuth client ID: ').strip()
    client_secret = getpass.getpass('OAuth client secret (not shown while typing): ').strip()
    state = secrets.token_urlsafe(16)
    got = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get('state', [''])[0] == state:
                got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write('<h2>Done. You can close this tab and go back to the Terminal.</h2>'.encode())

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    redirect = f'http://127.0.0.1:{server.server_port}'
    auth = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode({
        'client_id': client_id, 'redirect_uri': redirect, 'response_type': 'code', 'scope': SCOPES,
        'access_type': 'offline', 'prompt': 'select_account consent', 'state': state})
    print('\nOpening Google. Choose the account and the Gainly channel, then Allow.')
    print('If the browser does not open, copy this address into it:\n' + auth + '\n')
    webbrowser.open(auth)
    while 'code' not in got and 'error' not in got:
        server.handle_request()
    if 'error' in got:
        raise SystemExit('Google said: ' + got['error'])

    body = urllib.parse.urlencode({'code': got['code'], 'client_id': client_id, 'client_secret': client_secret,
                                   'redirect_uri': redirect, 'grant_type': 'authorization_code'}).encode()
    with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=body)) as r:
        tok = json.loads(r.read().decode())
    if 'refresh_token' not in tok:
        raise SystemExit('Google gave no refresh token. Remove the app at myaccount.google.com/permissions and run again.')
    req = urllib.request.Request('https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true',
                                 headers={'Authorization': 'Bearer ' + tok['access_token']})
    with urllib.request.urlopen(req) as r:
        ch = json.loads(r.read().decode()).get('items', [])

    print('\nChannel:', ch[0]['snippet']['title'] if ch else '(none found: was the Gainly channel chosen?)')
    print('YT_REFRESH_TOKEN =', tok['refresh_token'])
    print('Do not share it. Put it, the client ID and the client secret in GitHub Secrets.')


if __name__ == '__main__':
    main()
