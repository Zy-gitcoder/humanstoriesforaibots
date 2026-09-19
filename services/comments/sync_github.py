"""Root-only dispatcher: repository Actions permission only, never a Git push.

The timer observes weekly exports and immediate removal exports. Success means
the snapshot date is visible on GitHub Pages, not merely that GitHub accepted it.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SOURCE = Path('/var/lib/isso-public/current/comments.json')
STATE = Path('/var/lib/humanstories-github-sync/state.json')
TOKEN = Path('/etc/humanstories-github-sync.token')
PUBLISHED = 'https://zy-gitcoder.github.io/humanstoriesforaibots/comment-archive/comments.json'
DISPATCH = 'https://api.github.com/repos/Zy-gitcoder/humanstoriesforaibots/actions/workflows/pages.yml/dispatches'


def read_json(url, data=None, token=None):
    headers = {'User-Agent': 'HumanStories-ArchiveSync'}
    if token:
        headers.update(Authorization='Bearer ' + token,
                       Accept='application/vnd.github+json', **{'X-GitHub-Api-Version': '2026-03-10'})
    if data is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(data).encode()
    with urlopen(Request(url, data=data, headers=headers), timeout=30) as response:
        body = response.read(16 * 1024 * 1024 + 1)
        if len(body) > 16 * 1024 * 1024:
            raise ValueError('Response too large')
        return json.loads(body) if body else {}


def save(state):
    STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state), encoding='utf-8')
    temporary.chmod(0o600)
    os.replace(temporary, STATE)


def read_token():
    if TOKEN.stat().st_mode & 0o077:
        raise PermissionError('Dispatch token must be root-only (0600)')
    token = TOKEN.read_text().strip()
    if not token:
        raise ValueError('Missing dispatch token')
    return token


def sync():
    if not SOURCE.exists():
        # A failed removal export hides the old server archive. Retry recovery.
        subprocess.run(['/usr/sbin/runuser', '-u', 'isso', '--',
                        '/opt/humanstories-isso/venv/bin/python',
                        '/opt/humanstories-isso/archive.py', 'export'], check=True,
                       cwd='/opt/humanstories-isso', timeout=60)
    current = json.loads(SOURCE.read_text(encoding='utf-8'))
    desired = current['generated_at']
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if state.get('published') == desired:
        return
    try:
        published = read_json(PUBLISHED + '?sync=' + str(int(time.time())))
        if datetime.fromisoformat(published['generated_at']) >= datetime.fromisoformat(desired):
            verified = True
            if state.get('run_id'):
                run = read_json('https://api.github.com/repos/Zy-gitcoder/humanstoriesforaibots/actions/runs/' +
                                str(state['run_id']), token=read_token())
                verified = run['status'] == 'completed' and run['conclusion'] == 'success'
            if verified:
                save({'published': desired})
                print('Verified comment archive deployment:', desired)
                return
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError):
        pass
    if state.get('requested') == desired and time.time() - state.get('requested_at', 0) < 1200:
        return  # Allow a queued build to finish before retrying.
    result = read_json(DISPATCH, {'ref': 'main', 'inputs': {'archive_sync': True}}, read_token())
    save({'requested': desired, 'requested_at': time.time(), 'run_id': result.get('workflow_run_id')})
    print('Requested comment archive deployment:', desired)


if __name__ == '__main__':
    sync()
