"""Behavior tests against real SQLite transactions and the WSGI endpoint."""
import concurrent.futures
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from werkzeug.test import Client
from werkzeug.wrappers import Response
from engagement import Engagement, public_counts


class EngagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'test.db'
        self.app = Engagement(lambda e,s: Response('isso passthrough')(e,s), self.db, {'essay':'Essay','other':'Other'})
        self.client = Client(self.app, Response)
        self.token = 'a' * 64

    def send(self, route, **fields):
        return self.client.post('/engagement/'+route, json=fields)

    def test_views_sessions_and_likes_are_independent(self):
        for _ in range(3):
            response = self.send('view',post='essay',token=self.token)
            self.assertEqual(response.json['views'],1)
        response = self.send('view',post='essay',token='b'*64)
        self.assertEqual(response.json['views'],2)
        for _ in range(3):
            response = self.send('like',post='essay',token=self.token,liked=True)
            self.assertEqual(response.json['likes'],1)
        self.assertEqual(response.json['views'],2)
        self.assertTrue(self.send('state',token=self.token).json['posts']['essay']['liked'])
        self.assertFalse(self.send('state',token='b'*64).json['posts']['essay']['liked'])
        for _ in range(3):
            self.assertEqual(self.send('like',post='essay',token=self.token,liked=False).json['likes'],0)
        self.assertEqual(self.send('view',post='other',token=self.token).json['views'],1)

    def test_concurrent_retries_do_not_inflate_counts(self):
        def submit(_):
            c = Client(self.app,Response)
            view = c.post('/engagement/view',json={'post':'essay','token':self.token})
            like = c.post('/engagement/like',json={'post':'essay','token':self.token,'liked':True})
            return view.status_code,like.status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            self.assertEqual(set(executor.map(submit,range(30))),{(200,200)})
        counts = self.client.get('/engagement/stats').json['posts']['essay']
        self.assertEqual(counts,{'views':1,'likes':1,'revision':2})

    def test_validation_origin_and_existing_isso(self):
        self.assertEqual(self.client.get('/config').data,b'isso passthrough')
        self.assertEqual(self.send('view',post='wordpress-essay',token=self.token).status_code,404)
        self.assertEqual(self.send('view',post='essay',token='invalid').status_code,400)
        self.assertEqual(self.send('like',post='essay',token=self.token,liked=1).status_code,400)
        self.assertEqual(self.send('view',post='essay',token=self.token,extra='x').status_code,400)
        self.assertEqual(self.client.post('/engagement/like',data=b'x'*1025,content_type='application/json').status_code,413)
        self.assertEqual(self.client.post('/engagement/like',data=b'[]',content_type='application/json').status_code,400)
        self.assertEqual(self.client.get('/engagement/stats',headers={'Origin':'https://humanstoriesforaibots.com'}).status_code,403)
        cors=self.client.open('/engagement/like',method='OPTIONS',headers={'Origin':'https://zy-gitcoder.github.io'})
        self.assertEqual(cors.headers['Access-Control-Allow-Origin'],'https://zy-gitcoder.github.io')
        self.assertNotIn('Set-Cookie',cors.headers)

    def test_persistence_backup_and_public_export_excludes_identifiers(self):
        self.send('view',post='essay',token=self.token)
        self.send('like',post='essay',token=self.token,liked=True)
        restarted=Client(Engagement(self.app,self.db,{'essay':'Essay'}),Response)
        self.assertTrue(restarted.post('/engagement/state',json={'token':self.token}).json['posts']['essay']['liked'])
        with sqlite3.connect(self.db) as db, sqlite3.connect(':memory:') as copy:
            db.backup(copy)
            public=public_counts(copy)
            self.assertEqual(public['essay']['likes'],1)
            self.assertNotIn(self.token,json.dumps(list(db.execute('SELECT * FROM mirror_likes'))))
        self.assertNotIn('token',json.dumps(public))
        self.assertNotIn('hash',json.dumps(public))


if __name__ == '__main__':
    unittest.main(verbosity=2)
