"""Validate public comments and build a replaceable archive, never essay source.

Only the standard library is needed. Comment text is rendered literally and escaped.
"""
from datetime import datetime, timezone
from html import escape
import json
import math
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 16 * 1024 * 1024


def posts(root=ROOT):
    result = {}
    for path in (root / 'posts').glob('*.md'):
        front = path.read_text(encoding='utf-8').split('---', 2)[1]
        slug = re.search(r'^slug: ([a-z0-9-]+)$', front, re.M)[1]
        raw = re.search(r'^title: (.+)$', front, re.M)[1]
        title = json.loads(raw) if raw.startswith('"') else raw.strip("'")
        result[slug] = title
    return result


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Invalid snapshot date')
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Snapshot date must include timezone')
    return date


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 253402300799


def validate(payload, titles):
    if not isinstance(payload, dict) or payload.get('schema') != 1:
        raise ValueError('Unsupported public archive schema')
    timestamp(payload.get('generated_at'))
    if not isinstance(payload.get('comments'), list) or not isinstance(payload.get('removals'), list):
        raise ValueError('Missing comments or removal ledger')
    removals = {}
    for r in payload['removals']:
        if not isinstance(r, dict) or type(r.get('id')) is not int or r['id'] < 1 or not number(r.get('created')):
            raise ValueError('Invalid removal identity')
        if not isinstance(r.get('removed_at'), str) or len(r['removed_at']) > 64:
            raise ValueError('Invalid removal date')
        removals[r['id']] = {k: r[k] for k in ('id', 'created', 'removed_at')}
    comments, ids = [], set()
    for c in payload['comments']:
        if not isinstance(c, dict) or type(c.get('id')) is not int or c['id'] < 1 or c['id'] in ids:
            raise ValueError('Invalid or duplicate comment ID')
        ids.add(c['id'])
        uri = c.get('uri', '')
        match = re.fullmatch(r'/github-mirror/([a-z0-9-]+)/', uri)
        if not match or match[1] not in titles:
            continue  # The pilot and other discussions never enter the mirror archive.
        if c.get('mode') not in (1, 4) or not number(c.get('created')):
            raise ValueError('Invalid comment status/date')
        parent = c.get('parent')
        if parent is not None and (type(parent) is not int or parent < 1 or parent >= c['id']):
            raise ValueError('Invalid parent identity or cycle')
        if not isinstance(c.get('text'), str) or len(c['text']) > 2000:
            raise ValueError('Invalid comment text')
        author = c.get('author')
        if author is not None and (not isinstance(author, str) or len(author) > 64):
            raise ValueError('Invalid comment author')
        # Reconstruct an explicit public allowlist, even if upstream gains fields.
        clean = dict(id=c['id'], parent=parent, created=c['created'], mode=c['mode'],
                     text=c['text'], author=author, uri=uri, title=titles[match[1]])
        removal = removals.get(c['id'])
        if removal and removal['created'] != c['created']:
            raise ValueError('Reused comment ID conflicts with removal ledger')
        if clean['mode'] == 4 or removal:
            clean.update(mode=4, text='', author=None)
        comments.append(clean)
    by_id = {c['id']: c for c in comments}
    for c in comments:
        parent = by_id.get(c['parent'])
        if parent and parent['uri'] != c['uri']:
            raise ValueError('Cross-discussion parent')
        if c['parent'] is not None and not parent and c['parent'] not in removals:
            raise ValueError('Missing reply parent')
    return dict(schema=1, generated_at=payload['generated_at'],
                comments=sorted(comments, key=lambda c: c['id']),
                removals=sorted(removals.values(), key=lambda r: r['id']))


def reconcile(current, previous, titles):
    """Retain past removals; reject rollbacks, ID reuse and unexplained omissions."""
    current = validate(current, titles)
    if previous is None:
        return current
    previous = validate(previous, titles)
    if timestamp(current['generated_at']) < timestamp(previous['generated_at']):
        raise ValueError('Refusing an older snapshot')
    ledger = {r['id']: r for r in previous['removals']}
    for r in current['removals']:
        if r['id'] in ledger and ledger[r['id']]['created'] != r['created']:
            raise ValueError('Removal ID reuse')
        ledger[r['id']] = r
    current['removals'] = list(ledger.values())
    latest = {c['id']: c for c in current['comments']}
    for c in previous['comments']:
        new = latest.get(c['id'])
        if new and (new['created'], new['uri'], new['parent']) != (c['created'], c['uri'], c['parent']):
            raise ValueError('Comment identity changed')
        if new and c['mode'] == new['mode'] == 1 and (c['text'], c['author']) != (new['text'], new['author']):
            raise ValueError('Published comment was edited')
        if c['mode'] == 4 and new and new['mode'] != 4:
            new.update(mode=4, text='', author=None)
        if c['uri'].split('/')[2] in titles and new is None and c['id'] not in ledger:
            raise ValueError('Comment disappeared without a removal')
    return validate(current, titles)


def build(payload, titles, root=ROOT):
    payload = validate(payload, titles)
    folder = root / 'static/comment-archive'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'posts').mkdir(exist_ok=True)
    # Remove only generated per-essay Markdown from a previous local build.
    for path in (folder / 'posts').glob('*.md'):
        path.unlink()
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    (folder / 'comments.json').write_text(encoded, encoding='utf-8')
    groups = {slug: [] for slug in titles}
    for c in payload['comments']:
        item = dict(c)
        item['date'] = datetime.fromtimestamp(c['created'], timezone.utc).isoformat()
        groups[c['uri'].split('/')[2]].append(item)
    data = dict(generated_at=payload['generated_at'], threads=groups)
    (root / 'data').mkdir(exist_ok=True)
    (root / 'data/comment_archive.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Comment archive — Human Stories for AI Bots</title>',
             '<style>body{max-width:48rem;margin:3rem auto;padding:0 1rem;font:18px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #ccc;padding:1rem 0}</style>',
             '<h1>Comment archive</h1><p>Discussions are separate from the essays.</p>',
             '<p>Archived through ' + escape(payload['generated_at']) + '</p><p><a href="comments.zip">Download comments</a> · <a href="comments.json">JSON</a></p>']
    for slug, comments in groups.items():
        if not comments:
            continue
        parts.append('<h2>' + escape(titles[slug]) + '</h2><p><a href="posts/' + slug + '.md">Markdown</a></p>')
        md = ['# Discussion: ' + titles[slug], '', 'Thread: /github-mirror/' + slug + '/', '', 'Archived through: ' + payload['generated_at'], '']
        for c in comments:
            text = c['text'] if c['mode'] == 1 else '[Removed]'
            parent = ' · reply to #' + str(c['parent']) if c['parent'] else ''
            meta = f"#{c['id']} · {c['author'] or 'Anonymous'} · {c['date']}{parent}"
            parts.append(f'<article id="comment-{c["id"]}"><p>{escape(meta)}</p><pre>{escape(text)}</pre></article>')
            content = meta + '\n\n' + text
            fence = '`' * max(3, 1 + max((len(s) for s in re.findall(r'`+', content)), default=0))
            md.extend([f"## Comment {c['id']}", '', fence, content, fence, ''])
        (folder / 'posts' / (slug + '.md')).write_text('\n'.join(md), encoding='utf-8')
    if not payload['comments']:
        parts.append('<p>No mirror comments in this snapshot yet.</p>')
    parts.append('</html>')
    (folder / 'index.html').write_text('\n'.join(parts), encoding='utf-8')
    (folder / 'READ-ME.txt').write_text('Human Stories for AI Bots — separate comment archive\nOpen index.html offline. comments.json preserves IDs, reply relationships and removal records. posts/ contains per-essay Markdown. Essay text is not included.\n', encoding='utf-8')
    with zipfile.ZipFile(folder / 'comments.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and path.name != 'comments.zip':
                if path.name == 'index.html':
                    bundle.writestr('index.html', path.read_text(encoding='utf-8').replace('<a href="comments.zip">Download comments</a> · ', ''))
                else:
                    bundle.write(path, path.relative_to(folder).as_posix())
    print(f"Prepared {len(payload['comments'])} mirror comments; archive date {payload['generated_at']}")
