from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from comment_archive import build, reconcile, validate
import sync_comments

TITLES = {'essay': 'An essay', 'second': 'Another essay'}


def comment(id=1, parent=None, **extra):
    return dict(id=id, parent=parent, created=1000 + id, mode=1,
                text='Hello <script>alert(1)</script> 😀', author='Reader',
                uri='/github-mirror/essay/', title='Untrusted title', **extra)


def snapshot(comments=None, removals=None, date='2026-09-19T00:00:00+00:00'):
    return dict(schema=1, generated_at=date, comments=comments or [], removals=removals or [])


class ArchiveTests(unittest.TestCase):
    def test_allowlist_and_pilot_exclusion(self):
        pilot = comment(2)
        pilot['uri'] = '/pilot/'
        p = validate(snapshot([comment(email='private@example.com', remote_addr='private'), pilot]), TITLES)
        self.assertEqual(len(p['comments']), 1)
        self.assertNotIn('email', p['comments'][0])
        self.assertNotIn('remote_addr', p['comments'][0])
        self.assertEqual(p['comments'][0]['title'], 'An essay')

    def test_removal_survives_later_snapshot(self):
        removal = dict(id=1, created=1001, removed_at='2026-09-19 00:00:00')
        old = snapshot([comment()], [removal])
        p = reconcile(snapshot([comment()], date='2026-09-20T00:00:00+00:00'), old, TITLES)
        self.assertEqual(p['comments'][0]['mode'], 4)
        self.assertEqual(p['comments'][0]['text'], '')
        self.assertIsNone(p['comments'][0]['author'])

    def test_broken_reply_and_identity_rejected(self):
        cases = [snapshot([comment(), comment()]), snapshot([comment(2, 2)]),
                 snapshot([comment(2, 1)]), snapshot([comment(), {**comment(2, 1), 'uri': '/github-mirror/second/'}]),
                 snapshot([{**comment(), 'text': 'x' * 2001}])]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate(case, TITLES)
        with self.assertRaises(ValueError):
            reconcile(snapshot([]), snapshot([comment()]), TITLES)
        with self.assertRaises(ValueError):
            reconcile(snapshot([{**comment(), 'created': 5555}]), snapshot([comment()]), TITLES)
        with self.assertRaises(ValueError):
            reconcile(snapshot(date='2026-09-18T00:00:00+00:00'), snapshot(), TITLES)

    def test_escaped_separate_download_and_removed_parent(self):
        removal = dict(id=1, created=1001, removed_at='2026-09-19 00:00:00')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build(snapshot([comment(), comment(2, 1)], [removal]), TITLES, root)
            folder = root / 'static/comment-archive'
            html = (folder / 'index.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>', html)
            self.assertIn('&lt;script&gt;', html)
            self.assertIn('[Removed]', html)
            self.assertIn('reply to #1', html)
            with zipfile.ZipFile(folder / 'comments.zip') as z:
                self.assertIn('posts/essay.md', z.namelist())
                self.assertNotIn('source/posts/essay.md', z.namelist())
                self.assertEqual(json.loads(z.read('comments.json'))['comments'][0]['text'], '')

    def test_failed_fetch_falls_back_but_required_refresh_fails(self):
        previous = snapshot([comment()])
        with patch.object(sync_comments, 'posts', return_value=TITLES), \
             patch.object(sync_comments, 'previous_snapshot', return_value=previous), \
             patch.object(sync_comments, 'request', side_effect=TimeoutError), \
             patch.object(sync_comments, 'build') as render:
            sync_comments.prepare()
            self.assertEqual(render.call_args.args[0], previous)
            with self.assertRaises(RuntimeError):
                sync_comments.prepare(require_fresh=True)

    def test_essay_zip_omits_discussions(self):
        import package_archive
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public = root / 'public'
            public.mkdir()
            (root / 'posts').mkdir()
            for name in ['README.md', 'about.md', 'welcome.md']:
                (root / name).write_text('Essay material')
            (public / 'index.html').write_text('<p>Essay remains.</p><!-- discussion:start --><section>UniqueCommentText</section><!-- discussion:end -->')
            (public / 'comment-archive').mkdir()
            (public / 'comment-archive/comments.json').write_text('UniqueCommentText')
            with patch.object(package_archive, 'ROOT', root), patch.object(package_archive, 'PUBLIC', public):
                package_archive.main()
            with zipfile.ZipFile(public / 'archive.zip') as z:
                self.assertNotIn('comment-archive/comments.json', z.namelist())
                self.assertIn(b'Essay remains.', z.read('index.html'))
                self.assertNotIn(b'UniqueCommentText', z.read('index.html'))


if __name__ == '__main__':
    unittest.main()
