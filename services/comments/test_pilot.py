"""Integration tests against Isso 0.14.0 using a disposable database."""
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from isso import config, make_app
from werkzeug.test import Client, EnvironBuilder
from werkzeug.wrappers import Response
from gateway import Policy
import archive


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        archive.DB = cls.base / 'comments.db'
        archive.PUBLIC = cls.base / 'public'
        conf = cls.base / 'isso.cfg'
        conf.write_text(f'[general]\ndbpath={archive.DB}\nhost=\n http://127.0.0.1:8080/\n https://zy-gitcoder.github.io/\nnotify=\n[guard]\nenabled=false\n', encoding='utf-8')
        cls.native = make_app(config.load(config.default_file(), conf))
        # Apply the exact deployment migration to the disposable schema.
        source = Path('initialize.py').read_text()
        source = source[source.index('with sqlite3.connect('):]
        source = source.replace("conf.get('general', 'dbpath')", 'archive.DB')
        exec(source, {'sqlite3': sqlite3, 'archive': archive})
        cls.client = Client(Policy(cls.native, archive.refresh_after_removal,
            {'/github-mirror/essay-one/':'Essay one','/github-mirror/essay-two/':'Essay two'}, archive.DB), Response)

    def post(self, text, **extra):
        return self.client.post('/new?uri=/pilot/', json={'text': text, **extra}, headers={'Origin':'http://127.0.0.1:8080'})

    def test_01_unicode_boundaries_and_replies(self):
        for char in ('x', '文', '😀'):
            response = self.post(char * 2000, author='名' * 64)
            self.assertEqual(response.status_code, 201, response.data)
            root = response.json['id']
            self.assertEqual(self.post(char * 2001).status_code, 400)
        reply = self.post('A reply', parent=root)
        self.assertEqual(reply.status_code, 201, reply.data)
        self.assertEqual(reply.json['parent'], root)
        self.assertEqual(self.post('Valid body', author='x' * 65).status_code, 400)

    def test_02_request_limits_and_types(self):
        cases = [(b'x' * 32769, 413), (b'[]', 400), (b'{"text":"\\ud800"}', 400), (b'{"text":42}', 400)]
        for data, status in cases:
            response = self.client.post('/new?uri=/pilot/', data=data, content_type='application/json')
            self.assertEqual(response.status_code, status, response.data)
        self.assertEqual(self.post('Hello', email='no@example.org').status_code, 400)
        self.assertEqual(self.client.post('/new?uri=/other/', json={'text':'hello'}).status_code, 400)
        self.assertEqual(self.client.post('/new?uri=/pilot/', json={'text':'hello'}, headers={'Content-Encoding':'gzip'}).status_code, 415)
        env = EnvironBuilder(path='/new', method='POST').get_environ()
        env.pop('CONTENT_LENGTH', None)
        status = []
        list(Policy(self.native)(env, lambda s,h,e=None: status.append(s)))
        self.assertTrue(status[0].startswith('411'), status)

    def test_03_edit_and_html(self):
        c = self.post('<script>alert(1)</script> ![image](https://example.org/image.png) **bold**')
        self.assertEqual(c.status_code, 201, c.data)
        self.assertNotIn('<script>', c.json['text'])
        self.assertNotIn('<img', c.json['text'])
        id = c.json['id']
        for method, path in [('PUT',f'/id/{id}'),('PATCH',f'/id/{id}'),('POST',f'/id/{id}/edit/key'),('GET',f'/id/{id}/edit/key')]:
            self.assertEqual(self.client.open(path, method=method, json={'text':'changed'}).status_code, 405)
        with sqlite3.connect(archive.DB) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('UPDATE comments SET text=? WHERE id=?', ('rewritten',id))

    def test_04_export_delete_restore_and_fallback(self):
        c = self.post('Text that will be removed', author='<script>name</script>')
        self.assertEqual(c.status_code, 201, c.data)
        id = c.json['id']
        private = self.base / 'backup.db'
        archive.backup(private)
        archive.export()
        archive.delete(id, 'Pilot removal test')
        manifest = archive.PUBLIC / 'current/comments.json'
        data = json.loads(manifest.read_text())
        self.assertIn(id, [r['id'] for r in data['removals']])
        for comment in data['comments']:
            self.assertFalse(set(comment) & {'email','remote_addr','voters','hash','notification'})
        with zipfile.ZipFile(archive.PUBLIC / 'current/comments.zip') as z:
            for name in z.namelist():
                self.assertNotIn(b'Text that will be removed', z.read(name))
        original = archive.DB
        archive.DB = self.base / 'restored.db'
        try:
            archive.restore(private, manifest)
            with sqlite3.connect(archive.DB) as db:
                self.assertEqual(db.execute('SELECT mode,text FROM comments WHERE id=?',(id,)).fetchone(), (4,''))
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            archive.DB = self.base / 'missing.db'
            old = manifest.read_bytes()
            with self.assertRaises(sqlite3.OperationalError):
                archive.export()
            self.assertEqual(manifest.read_bytes(), old)
        finally:
            archive.DB = original

    def test_05_author_delete_and_monotonic_ids(self):
        first = self.post('Disposable author removal')
        id = first.json['id']
        response = self.client.delete(f'/id/{id}', headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(id, [r['id'] for r in json.loads((archive.PUBLIC / 'current/comments.json').read_text())['removals']])
        second = self.post('A fresh comment ID')
        self.assertGreater(second.json['id'], id)

    def test_06_cross_origin(self):
        response = self.client.get('/config', headers={'Origin':'https://zy-gitcoder.github.io'})
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), 'https://zy-gitcoder.github.io')

    def test_07_failed_removal_refresh_hides_old_edition(self):
        archive.export()
        self.assertTrue((archive.PUBLIC / 'current').exists())
        with patch.object(archive, 'export', side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):
                archive.refresh_after_removal()
        self.assertFalse((archive.PUBLIC / 'current').exists())
        response = self.client.post('/new?uri=/pilot/', json={'text':'x'*2001}, headers={'Origin':'https://zy-gitcoder.github.io'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), 'https://zy-gitcoder.github.io')

    def test_08_mirror_thread_separation(self):
        one='/github-mirror/essay-one/'
        two='/github-mirror/essay-two/'
        root=self.client.post('/new?uri='+one, json={'text':'Mirror discussion one','title':'Client cannot rename this'},headers={'Origin':'https://zy-gitcoder.github.io'})
        self.assertEqual(root.status_code,201,root.data)
        parent=root.json['id']
        reply=self.client.post('/new?uri='+one,json={'text':'A reply on the same essay','parent':parent})
        self.assertEqual(reply.status_code,201,reply.data)
        self.assertEqual(reply.json['parent'],parent)
        rejected=self.client.post('/new?uri='+two,json={'text':'Wrong discussion','parent':parent})
        self.assertEqual(rejected.status_code,400)
        for value in (True,-1,10**100,999999):
            self.assertEqual(self.client.post('/new?uri='+one,json={'text':'Invalid parent','parent':value}).status_code,400)
        self.assertEqual(self.client.post('/new?uri=/2026/01/01/essay-one/',json={'text':'Original blog path is not a mirror discussion'}).status_code,400)
        self.assertEqual(self.client.post('/new?uri='+one+'&uri='+two,json={'text':'Ambiguous thread'}).status_code,400)
        self.assertEqual(self.client.get('/?uri='+two).json['total_replies'],0)
        self.assertEqual(self.client.get('/?uri='+one).json['total_replies'],2)
        with sqlite3.connect(archive.DB) as db:
            self.assertEqual(db.execute('SELECT title FROM threads WHERE uri=?',(one,)).fetchone()[0],'Essay one')
        archive.export()
        public=json.loads((archive.PUBLIC/'current/comments.json').read_text())
        exported=[c for c in public['comments'] if c['uri']==one]
        self.assertEqual(len(exported),2)
        self.assertEqual(exported[1]['parent'],parent)
        self.assertIn('Essay one',(archive.PUBLIC/'current/index.html').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
