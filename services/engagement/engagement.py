"""Independent GitHub-mirror views and likes; no accounts, cookies or IP IDs."""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time

ORIGINS = {'https://zy-gitcoder.github.io', 'https://comments.humanstoriesforaibots.com'}
TOKEN = re.compile(r'[a-f0-9]{64}\Z')


def initialize(db_path):
    with sqlite3.connect(db_path, timeout=10) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS mirror_counts (
          post TEXT PRIMARY KEY, views INTEGER NOT NULL DEFAULT 0,
          likes INTEGER NOT NULL DEFAULT 0 CHECK(likes>=0), revision INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS mirror_views (
          post TEXT NOT NULL, token_hash TEXT NOT NULL, seen_at REAL NOT NULL,
          PRIMARY KEY(post,token_hash));
        CREATE INDEX IF NOT EXISTS mirror_views_age ON mirror_views(seen_at);
        CREATE TABLE IF NOT EXISTS mirror_likes (
          post TEXT NOT NULL, token_hash TEXT NOT NULL, PRIMARY KEY(post,token_hash));
        ''')


def public_counts(db):
    return {r[0]: {'views': r[1], 'likes': r[2], 'revision': r[3]}
            for r in db.execute('SELECT post,views,likes,revision FROM mirror_counts ORDER BY post')}


class Engagement:
    def __init__(self, app, db_path, posts):
        self.app, self.db_path, self.posts = app, str(db_path), dict(posts)
        initialize(self.db_path)

    def __call__(self, env, start_response):
        path = env.get('PATH_INFO', '')
        if not path.startswith('/engagement/'):
            return self.app(env, start_response)
        method = env['REQUEST_METHOD']
        origin = env.get('HTTP_ORIGIN')
        def respond(status, payload):
            body = json.dumps(payload, ensure_ascii=True).encode()
            headers = [('Content-Type','application/json'), ('Content-Length',str(len(body))),
                       ('Cache-Control','no-store'), ('Vary','Origin')]
            if origin in ORIGINS:
                headers += [('Access-Control-Allow-Origin',origin),
                            ('Access-Control-Allow-Methods','GET, POST, OPTIONS'),
                            ('Access-Control-Allow-Headers','Content-Type'),
                            ('Access-Control-Max-Age','600')]
            start_response(status, headers)
            return [body]
        if origin and origin not in ORIGINS:
            return respond('403 Forbidden', {'error':'This endpoint belongs to the GitHub mirror.'})
        routes = {'/engagement/stats','/engagement/state','/engagement/view','/engagement/like'}
        if path not in routes:
            return respond('404 Not Found', {'error':'Unknown endpoint.'})
        if method == 'OPTIONS':
            return respond('200 OK', {})
        if path == '/engagement/stats':
            if method != 'GET':
                return respond('405 Method Not Allowed', {'error':'Use GET.'})
            with sqlite3.connect(self.db_path, timeout=10) as db:
                counts = public_counts(db)
            return respond('200 OK', {'scope':'github-mirror','posts':{
                p: counts.get(p, {'views':0,'likes':0,'revision':0}) for p in self.posts}})
        if method != 'POST':
            return respond('405 Method Not Allowed', {'error':'Use POST.'})
        if env.get('HTTP_CONTENT_ENCODING') or env.get('HTTP_TRANSFER_ENCODING'):
            return respond('415 Unsupported Media Type', {'error':'Use unencoded JSON.'})
        try:
            size = int(env.get('CONTENT_LENGTH') or '-1')
        except ValueError:
            size = -1
        if size < 0:
            return respond('411 Length Required', {'error':'Content-Length is required.'})
        if size > 1024:
            return respond('413 Content Too Large', {'error':'Maximum body is 1 KiB.'})
        if env.get('CONTENT_TYPE','').split(';')[0].strip() != 'application/json':
            return respond('415 Unsupported Media Type', {'error':'Use application/json.'})
        try:
            raw = env['wsgi.input'].read(size)
            if len(raw) != size:
                raise ValueError()
            data = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeError, RecursionError):
            return respond('400 Bad Request', {'error':'Malformed JSON.'})
        fields = {'token'} if path.endswith('/state') else {'token','post'}
        if path.endswith('/like'):
            fields.add('liked')
        if not isinstance(data, dict) or set(data) != fields:
            return respond('400 Bad Request', {'error':'Unexpected or missing fields.'})
        if not isinstance(data['token'],str) or not TOKEN.fullmatch(data['token']):
            return respond('400 Bad Request', {'error':'Use a random 64-character lowercase hexadecimal token.'})
        if 'post' in fields and (not isinstance(data['post'],str) or data['post'] not in self.posts):
            return respond('404 Not Found', {'error':'Unknown mirror essay.'})
        if 'liked' in fields and type(data['liked']) is not bool:
            return respond('400 Bad Request', {'error':'liked must be true or false.'})
        def digest(post):
            # Per-post hashes cannot be joined to follow a token across essays.
            return hashlib.sha256(('github-mirror\0'+post+'\0'+data['token']).encode()).hexdigest()
        try:
            with sqlite3.connect(self.db_path, timeout=10) as db:
                if path.endswith('/state'):
                    db.execute('BEGIN')
                    counts = public_counts(db)
                    result = {}
                    for post in self.posts:
                        result[post] = dict(counts.get(post, {'views':0,'likes':0,'revision':0}),
                            liked=db.execute('SELECT 1 FROM mirror_likes WHERE post=? AND token_hash=?',
                                             (post,digest(post))).fetchone() is not None)
                    return respond('200 OK', {'scope':'github-mirror','posts':result})
                post, key = data['post'], digest(data['post'])
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT OR IGNORE INTO mirror_counts(post) VALUES(?)', (post,))
                if path.endswith('/view'):
                    # Count once per session token; retain deduplication records 30 days.
                    inserted = db.execute('INSERT OR IGNORE INTO mirror_views VALUES(?,?,?)',
                                          (post,key,time.time())).rowcount
                    if inserted:
                        db.execute('UPDATE mirror_counts SET views=views+1,revision=revision+1 WHERE post=?',(post,))
                    db.execute('DELETE FROM mirror_views WHERE seen_at<?', (time.time()-30*86400,))
                else:
                    if data['liked']:
                        changed = db.execute('INSERT OR IGNORE INTO mirror_likes VALUES(?,?)',(post,key)).rowcount
                    else:
                        changed = -db.execute('DELETE FROM mirror_likes WHERE post=? AND token_hash=?',(post,key)).rowcount
                    if changed:
                        db.execute('UPDATE mirror_counts SET likes=likes+?,revision=revision+1 WHERE post=?',(changed,post))
                result = public_counts(db)[post]
                if path.endswith('/like'):
                    result['liked'] = data['liked']
            return respond('200 OK', dict(result,post=post,scope='github-mirror'))
        except sqlite3.OperationalError:
            return respond('503 Service Unavailable', {'error':'Temporarily unavailable. Please retry.'})


def wrap(app, db_path):
    posts = json.loads(Path('/opt/humanstories-isso/mirror-posts.json').read_text(encoding='utf-8'))
    return Engagement(app, db_path, posts)
