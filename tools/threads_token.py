"""Get a long-lived Threads access token for the Gainly Threads profile. Run it on your own computer:

    python3 tools/threads_token.py

It asks for the Threads App ID and App Secret (Meta app > Use cases > Threads > Settings), opens the Threads
"allow" page in your browser, and after you paste back the address you land on, prints the token and your
Threads user ID. Put them in GitHub > Settings > Secrets > Actions as THREADS_TOKEN and THREADS_USER_ID.
Nothing is saved or sent anywhere except to Threads itself. The token lasts 60 days, the daily job renews it.
"""
import getpass
import json
import urllib.parse
import urllib.request
import webbrowser

REDIRECT = 'https://gainly.in/'
SCOPES = 'threads_basic,threads_content_publish,threads_read_replies,threads_manage_replies,threads_manage_insights'


def call(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    with urllib.request.urlopen(urllib.request.Request(url, data=body)) as r:
        return json.loads(r.read().decode())


def main():
    app_id = input('Threads App ID: ').strip()
    secret = getpass.getpass('Threads App Secret (not shown while typing): ').strip()
    auth = 'https://threads.net/oauth/authorize?' + urllib.parse.urlencode(
        {'client_id': app_id, 'redirect_uri': REDIRECT, 'scope': SCOPES, 'response_type': 'code'})
    print('\nOpening Threads. Log in as Gainly and press Allow. You will land on gainly.in.')
    print('If the browser does not open, copy this address into it:\n' + auth + '\n')
    webbrowser.open(auth)
    back = input('Paste the full gainly.in address from the browser here: ').strip()
    code = urllib.parse.parse_qs(urllib.parse.urlparse(back).query).get('code', [''])[0].split('#')[0]
    if not code:
        raise SystemExit('No "code" in that address. Run the script again and paste the whole address.')

    short = call('https://graph.threads.net/oauth/access_token', {
        'client_id': app_id, 'client_secret': secret, 'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT, 'code': code})
    long = call('https://graph.threads.net/access_token?' + urllib.parse.urlencode(
        {'grant_type': 'th_exchange_token', 'client_secret': secret, 'access_token': short['access_token']}))
    me = call('https://graph.threads.net/v1.0/me?' + urllib.parse.urlencode(
        {'fields': 'id,username', 'access_token': long['access_token']}))

    print('\nDone for @' + me.get('username', '?'))
    print('THREADS_USER_ID =', me['id'])
    print('THREADS_TOKEN   =', long['access_token'])
    print('Valid for about', int(long.get('expires_in', 0)) // 86400, 'days. Do not share the token.')


if __name__ == '__main__':
    main()
