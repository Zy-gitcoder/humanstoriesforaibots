"""Small, fail-closed policy layer for the pinned Isso pilot."""
import io
import json
import re
import sqlite3
from urllib.parse import parse_qs

MAX_BODY = 32768
THREAD = '/pilot/'


class Policy:
    def __init__(self, app, on_delete=lambda: None, threads=None, db_path=None):
        self.app, self.on_delete = app, on_delete
        self.threads = {THREAD: 'Human Stories comment pilot', **(threads or {})}
        self.db_path = db_path

    def __call__(self, env, start_response):
        original_start = start_response
        def start_response(status, headers, exc_info=None):
            origin = env.get('HTTP_ORIGIN')
            if origin in ('https://zy-gitcoder.github.io', 'https://comments.humanstoriesforaibots.com', 'http://127.0.0.1:8080'):
                names = {k.lower() for k, _ in headers}
                if 'access-control-allow-origin' not in names:
                    headers += [('Access-Control-Allow-Origin', origin), ('Access-Control-Allow-Credentials', 'true')]
                headers += [('Vary', 'Origin')]
            return original_start(status, headers, exc_info)
        method, path = env['REQUEST_METHOD'], env.get('PATH_INFO', '/')
        def reject(status, message):
            body = json.dumps({'error': message}).encode()
            start_response(status, [('Content-Type', 'application/json'),
                                     ('Content-Length', str(len(body))),
                                     ('Cache-Control', 'no-store')])
            return [body]

        # No author or administrator edit route can reach Isso.
        if method in ('PUT', 'PATCH') or '/edit/' in path:
            return reject('405 Method Not Allowed', 'Comments cannot be edited. Please write a reply.')
        if path.startswith(('/admin', '/login', '/demo')) or re.search(r'/id/\d+/(activate|delete)/', path):
            return reject('403 Forbidden', 'Administration uses SSH for this pilot.')
        permitted = (
            method in ('GET', 'HEAD', 'OPTIONS') or
            (method == 'POST' and (path in ('/new', '/preview', '/count') or
                                  re.fullmatch(r'/id/\d+/(like|dislike)', path))) or
            (method == 'DELETE' and re.fullmatch(r'/id/\d+', path))
        )
        if not permitted:
            return reject('405 Method Not Allowed', 'Unsupported method or endpoint.')

        if method == 'POST':
            if env.get('HTTP_CONTENT_ENCODING') or env.get('HTTP_TRANSFER_ENCODING'):
                return reject('415 Unsupported Media Type', 'Encoded bodies are not accepted.')
            try:
                size = int(env.get('CONTENT_LENGTH') or '-1')
            except ValueError:
                size = -1
            if size < 0:
                return reject('411 Length Required', 'Content-Length is required.')
            if size > MAX_BODY:
                return reject('413 Content Too Large', 'Request body exceeds 32 KiB.')
            raw = env['wsgi.input'].read(size)
            if len(raw) != size:
                return reject('400 Bad Request', 'Incomplete request body.')
            if path in ('/new', '/preview', '/count'):
                if env.get('CONTENT_TYPE', '').split(';')[0].strip() != 'application/json':
                    return reject('415 Unsupported Media Type', 'Use application/json.')
                try:
                    data = json.loads(raw.decode('utf-8'))
                    # Reject unpaired surrogate escapes as well as malformed UTF-8.
                    json.dumps(data, ensure_ascii=False).encode('utf-8')
                except (ValueError, UnicodeError, RecursionError):
                    return reject('400 Bad Request', 'Valid UTF-8 JSON is required.')
                if path == '/count':
                    if not isinstance(data, list) or len(data) > 100 or not all(isinstance(s, str) and len(s) <= 256 for s in data):
                        return reject('400 Bad Request', 'Provide at most 100 short thread paths.')
                else:
                    if not isinstance(data, dict):
                        return reject('400 Bad Request', 'JSON must be an object.')
                    limits = {'text': 2000, 'author': 64, 'title': 200, 'email': 254, 'website': 254}
                    if set(data) - (set(limits) | {'parent', 'notification'}):
                        return reject('400 Bad Request', 'Unknown comment fields.')
                    if not isinstance(data.get('text'), str) or len(data['text'].rstrip()) < 3:
                        return reject('400 Bad Request', 'A comment needs at least 3 characters.')
                    for field, limit in limits.items():
                        value = data.get(field)
                        if value is not None and (not isinstance(value, str) or len(value) > limit):
                            return reject('400 Bad Request', f'{field} must contain at most {limit} Unicode code points.')
                    # This pilot deliberately does not collect email or enable notifications.
                    if data.get('email') or data.get('notification'):
                        return reject('400 Bad Request', 'Email notifications are disabled in this pilot.')
                    if path == '/new':
                        uris = parse_qs(env.get('QUERY_STRING', '')).get('uri', [])
                        if len(uris) != 1 or uris[0] not in self.threads:
                            return reject('400 Bad Request', 'Unknown discussion. Use a published mirror essay or /pilot/.')
                        uri = uris[0]
                        parent = data.get('parent')
                        if parent is not None:
                            if type(parent) is not int or not 0 < parent <= 2**63-1:
                                return reject('400 Bad Request', 'parent must be a positive comment ID or null.')
                            if self.db_path:
                                with sqlite3.connect(self.db_path, timeout=10) as db:
                                    row = db.execute('SELECT t.uri FROM comments c JOIN threads t ON t.id=c.tid WHERE c.id=?', (parent,)).fetchone()
                                if row is None or row[0] != uri:
                                    return reject('400 Bad Request', 'A reply must belong to the same essay as its parent.')
                        data['title'] = self.threads[uri]
                        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
            env['wsgi.input'] = io.BytesIO(raw)
            env['CONTENT_LENGTH'] = str(len(raw))

        if method == 'DELETE':
            response = {}
            def capture(status, headers, exc_info=None):
                response.update(status=status, headers=headers, exc_info=exc_info)
            result = self.app(env, capture)
            try:
                body = list(result)
            finally:
                if hasattr(result, 'close'):
                    result.close()
            if response['status'].startswith('2'):
                self.on_delete()
            start_response(response['status'], response['headers'], response['exc_info'])
            return body
        return self.app(env, start_response)
