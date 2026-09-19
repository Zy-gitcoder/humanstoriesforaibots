"""Fetch public snapshots; keep a replaceable GitHub Release as off-server storage."""
import argparse
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from comment_archive import ROOT, MAX_BYTES, build, posts, reconcile, timestamp, validate

REPO = 'Zy-gitcoder/humanstoriesforaibots'
API = 'https://api.github.com/repos/' + REPO
TAG = 'comment-archive'
SOURCE = 'https://comments.humanstoriesforaibots.com/archive/comments.json'


def request(url, method='GET', data=None, content_type='application/json', authenticated=False):
    headers = {'User-Agent': 'HumanStories-CommentArchive', 'Accept': 'application/vnd.github+json'}
    if authenticated and os.environ.get('GITHUB_TOKEN'):
        if not url.startswith(('https://api.github.com/', 'https://uploads.github.com/')):
            raise ValueError('Credentials only go to GitHub API hosts')
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
        headers['X-GitHub-Api-Version'] = '2022-11-28'
    if data is not None:
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()
        headers['Content-Type'] = content_type
    with urlopen(Request(url, data=data, headers=headers, method=method), timeout=45) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('Archive response exceeds 16 MiB')
        return json.loads(body) if body else None


def release():
    try:
        return request(API + '/releases/tags/' + TAG, authenticated=True)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def assets(info):
    result, page = [], 1
    while True:
        rows = request(info['assets_url'] + f'?per_page=100&page={page}', authenticated=True)
        result.extend(rows)
        if len(rows) < 100:
            return result
        page += 1


def previous_snapshot(titles):
    info = release()
    if info is None:
        return None
    candidates = [a for a in assets(info) if a['name'] == 'comments.json' or
                  (a['name'].startswith('comments-next-') and a['name'].endswith('.json'))]
    if not candidates:
        raise ValueError('Archive release exists but has no recoverable JSON snapshot')
    valid = []
    for asset in candidates:
        try:
            # Public assets are downloaded without an Authorization header.
            data = request(asset['browser_download_url'])
            valid.append(validate(data, titles))
        except (HTTPError, URLError, ValueError):
            continue
    if not valid:
        raise ValueError('No valid previous release archive; refusing to overwrite it')
    return max(valid, key=lambda p: timestamp(p['generated_at']))


def prepare(require_fresh=False, input_file=None):
    titles = posts()
    if input_file:
        build(json.loads(Path(input_file).read_text(encoding='utf-8')), titles)
        return
    previous = previous_snapshot(titles)
    try:
        payload = reconcile(request(SOURCE), previous, titles)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        if previous is None or require_fresh:
            raise RuntimeError('Fresh archive required but unavailable or invalid') from exc
        print('Source unavailable or rejected; keeping last validated GitHub snapshot.')
        payload = previous
    build(payload, titles)


def publish():
    if not os.environ.get('GITHUB_TOKEN'):
        raise RuntimeError('GITHUB_TOKEN with repository contents:write is required')
    folder = ROOT / 'static/comment-archive'
    payload = validate(json.loads((folder / 'comments.json').read_text(encoding='utf-8')), posts())
    info = release()
    if info is None:
        info = request(API + '/releases', 'POST', dict(tag_name=TAG,
            target_commitish=os.environ.get('GITHUB_SHA', 'main'), name='Latest comment archive',
            body='Replaceable public discussion snapshot. JSON and a separate offline HTML/Markdown ZIP. Essay source is unchanged. This archive must remain mutable so removals can propagate.',
            draft=True, prerelease=False, make_latest='false'), authenticated=True)
    if info.get('immutable'):
        raise RuntimeError('Comment archive release is immutable; replacement is not possible')
    prior_assets = assets(info)
    nonce = str(time.time_ns())
    staged = []
    for extension, mime in [('json', 'application/json'), ('zip', 'application/zip')]:
        name = 'comments-next-' + nonce + '.' + extension
        url = info['upload_url'].split('{')[0] + '?name=' + name
        data = (folder / ('comments.' + extension)).read_bytes()
        asset = request(url, 'POST', data, mime, authenticated=True)
        if asset['size'] != len(data) or asset['state'] != 'uploaded':
            raise RuntimeError('Release upload verification failed')
        staged.append((asset, 'comments.' + extension))
    # Both replacement files are safely uploaded before retiring either old asset.
    for asset in prior_assets:
        if asset['name'] in ('comments.json', 'comments.zip') or asset['name'].startswith('comments-next-'):
            request(asset['url'], 'DELETE', authenticated=True)
    for asset, name in staged:
        request(asset['url'], 'PATCH', {'name': name}, authenticated=True)
    request(info['url'], 'PATCH', dict(draft=False, make_latest='false',
        body='Public mirror discussions, archived through ' + payload['generated_at'] +
             '. JSON preserves stable IDs and removal records; ZIP contains separate HTML and per-essay Markdown. This replaceable archive is independent of the essay download.'), authenticated=True)
    print('Published replaceable comment archive to GitHub Releases.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'publish'])
    parser.add_argument('--require-fresh', action='store_true')
    parser.add_argument('--input')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.require_fresh, args.input)
    else:
        publish()
