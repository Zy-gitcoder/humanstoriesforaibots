"""Public allowlist export, consistent private backup, and SSH-only deletion."""
import argparse
import datetime as dt
import fcntl
import html
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import zipfile

DB = Path(os.environ.get('ISSO_DB', '/var/lib/isso/comments.db'))
PUBLIC = Path(os.environ.get('ISSO_PUBLIC', '/var/lib/isso-public'))


def snapshot():
    source = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    dest = sqlite3.connect(':memory:')
    source.backup(dest)
    source.close()
    dest.row_factory = sqlite3.Row
    return dest


def export():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    with (PUBLIC / '.export.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with snapshot() as db:
            rows = db.execute('SELECT c.id,c.parent,c.created,c.modified,c.mode,c.text,c.author,c.likes,c.dislikes,t.uri,t.title FROM comments c JOIN threads t ON t.id=c.tid WHERE c.mode IN (1,4) ORDER BY c.id').fetchall()
            removals = [dict(r) for r in db.execute('SELECT id,created,removed_at FROM pilot_removals ORDER BY id')]
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='mirror_counts'").fetchone():
                from engagement import public_counts
                engagement = {'scope':'github-mirror','posts':public_counts(db)}
            else:
                engagement = {'scope':'github-mirror','posts':{}}
        comments = []
        for row in rows:
            c = dict(row)
            if c['mode'] == 4:
                c.update(text='', author=None, likes=0, dislikes=0)
            c['author'] = html.unescape(c['author']) if c['author'] else None
            comments.append(c)
        payload = {'schema': 1, 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'comments': comments, 'removals': removals}
        generation = Path(tempfile.mkdtemp(prefix='snapshot-', dir=PUBLIC))
        try:
            (generation / 'comments.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            engagement['generated_at'] = payload['generated_at']
            (generation / 'engagement.json').write_text(json.dumps(engagement, indent=2), encoding='utf-8')
            md = ['# Human Stories — archived comments', '', 'Snapshot: ' + payload['generated_at'], '']
            parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Archived comments — Human Stories</title><style>body{max-width:48rem;margin:3rem auto;padding:0 1rem;font:18px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #ccc;padding:1rem 0}h2{font-size:1.2rem}</style><h1>Archived comments</h1><p>Snapshot: ' + html.escape(payload['generated_at']) + '</p><p><a href="comments.md">Markdown</a> · <a href="comments.json">JSON</a> · <a href="comments.zip">Download archive</a></p>']
            for c in comments:
                author = c['author'] or 'Anonymous'
                text = c['text'] if c['mode'] == 1 else '[Removed]'
                meta = f"Comment {c['id']} · {author} · parent {c['parent']} · {c['created']} · likes {c['likes']}"
                fence = '`' * max(3, 1 + max((len(s) for s in re.findall(r'`+', text)), default=0))
                # User content remains a literal block: neither HTML nor Markdown can execute.
                metadata = json.dumps({k: c[k] for k in ('title', 'uri', 'author', 'parent', 'created', 'likes', 'mode')}, ensure_ascii=True)
                content = 'Metadata: ' + metadata + '\n\n' + text
                fence = '`' * max(3, 1 + max((len(s) for s in re.findall(r'`+', content)), default=0))
                md.extend([f"## Comment {c['id']}", '', fence, content, fence, ''])
                parts.append(f'<article id="comment-{c["id"]}"><h2>{html.escape(c["title"] or c["uri"])}</h2><p>Discussion: {html.escape(c["uri"])}</p><p>{html.escape(meta)}</p><pre>{html.escape(text)}</pre></article>')
            parts.append('</html>')
            (generation / 'comments.md').write_text('\n'.join(md), encoding='utf-8')
            (generation / 'index.html').write_text(''.join(parts), encoding='utf-8')
            with zipfile.ZipFile(generation / 'comments.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
                for name in ('index.html', 'comments.md', 'comments.json', 'engagement.json'):
                    bundle.write(generation / name, name)
            generation.chmod(0o755)
            for file in generation.iterdir():
                file.chmod(0o644)
            link = PUBLIC / '.next'
            link.unlink(missing_ok=True)
            link.symlink_to(generation.name, target_is_directory=True)
            old = (PUBLIC / 'current').resolve() if (PUBLIC / 'current').exists() else None
            os.replace(link, PUBLIC / 'current')
            if old and old != generation and old.parent == PUBLIC.resolve() and old.name.startswith('snapshot-'):
                shutil.rmtree(old)
        except BaseException:
            if not (PUBLIC / 'current').exists() or (PUBLIC / 'current').resolve() != generation:
                shutil.rmtree(generation)
            raise
    return len(comments)


def refresh_after_removal():
    try:
        export()
    except Exception:
        # A failed ordinary export keeps the last good snapshot. A removal is
        # different: take the old edition offline rather than expose removed text.
        (PUBLIC / 'current').unlink(missing_ok=True)
        raise


def delete(comment_id, reason):
    # Retain only an empty tombstone, so replies and comment identities remain stable.
    with sqlite3.connect(DB) as db:
        row = db.execute('SELECT id FROM comments WHERE id=?', (comment_id,)).fetchone()
        if not row:
            raise ValueError('Comment does not exist')
        db.execute("UPDATE comments SET mode=4,text='',author=NULL,email=NULL,website=NULL,remote_addr=NULL,likes=0,dislikes=0,voters=X'',notification=0 WHERE id=?", (comment_id,))
        db.execute('UPDATE pilot_removals SET reason=? WHERE id=?', (reason, comment_id))
    refresh_after_removal()


def backup(destination):
    dest = Path(destination)
    source = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    with sqlite3.connect(dest) as copy:
        source.backup(copy)
        if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup integrity check failed')
    source.close()
    dest.chmod(0o600)


def restore(backup_path, manifest_path):
    if DB.exists():
        raise ValueError('Restore only to a new database path with Isso stopped; never overwrite a running database.')
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    if manifest.get('schema') != 1 or 'removals' not in manifest:
        raise ValueError('A current public archive removal manifest is required.')
    shutil.copyfile(backup_path, DB)
    DB.chmod(0o600)
    with sqlite3.connect(DB) as db:
        for r in manifest['removals']:
            db.execute("UPDATE comments SET mode=4,text='',author=NULL,email=NULL,website=NULL,remote_addr=NULL,likes=0,dislikes=0,voters=X'',notification=0 WHERE id=? AND created=?", (r['id'], r['created']))
            db.execute('INSERT OR IGNORE INTO pilot_removals(id,created,removed_at) VALUES(?,?,?)', (r['id'], r['created'], r['removed_at']))
        # Reserve IDs that existed after the backup, including fully deleted comments.
        highest = max([0] + [c['id'] for c in manifest['comments']] + [r['id'] for r in manifest['removals']])
        db.execute("UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name='comments'", (highest,))
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Restored database failed integrity check')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('export')
    d = sub.add_parser('delete')
    d.add_argument('id', type=int)
    d.add_argument('--reason', required=True)
    b = sub.add_parser('backup')
    b.add_argument('destination')
    r = sub.add_parser('restore')
    r.add_argument('backup')
    r.add_argument('--current-manifest', required=True)
    args = parser.parse_args()
    if args.command == 'export':
        print(f'Exported {export()} comments/tombstones.')
    elif args.command == 'delete':
        delete(args.id, args.reason)
        print(f'Removed comment {args.id} and refreshed public archive.')
    elif args.command == 'backup':
        backup(args.destination)
        print('Consistent backup verified.')
    else:
        restore(args.backup, args.current_manifest)
        print('Restored backup with current removals reapplied.')
