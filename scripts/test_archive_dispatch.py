"""Exercise the retry/acknowledgement loop without GitHub credentials or writes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'services/comments/sync_github.py'
spec = importlib.util.spec_from_file_location('dispatcher', SOURCE)
dispatcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatcher)


class DispatcherTests(unittest.TestCase):
    def test_dispatch_retry_and_publication_confirmation(self):
        date = '2026-09-19T00:00:00+00:00'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, state = root / 'comments.json', root / 'state.json'
            source.write_text(json.dumps({'generated_at': date}))
            with patch.object(dispatcher, 'SOURCE', source), patch.object(dispatcher, 'STATE', state), \
                 patch.object(dispatcher, 'read_token', return_value='test-only'), \
                 patch.object(dispatcher, 'read_json') as api:
                api.side_effect = [TimeoutError(), {'workflow_run_id': 123}]
                dispatcher.sync()
                self.assertEqual(json.loads(state.read_text())['run_id'], 123)
                self.assertEqual(api.call_args.args[1], {'ref': 'main', 'inputs': {'archive_sync': True}})
                api.reset_mock()
                api.side_effect = [TimeoutError()]
                dispatcher.sync()
                self.assertEqual(api.call_count, 1)  # Do not repeatedly dispatch a queued build.
                api.side_effect = [{'generated_at': date}, {'status': 'in_progress', 'conclusion': None}]
                dispatcher.sync()
                self.assertNotIn('published', json.loads(state.read_text()))
                api.side_effect = [{'generated_at': date}, {'status': 'completed', 'conclusion': 'success'}]
                dispatcher.sync()
                self.assertEqual(json.loads(state.read_text()), {'published': date})
                api.reset_mock()
                dispatcher.sync()
                api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
