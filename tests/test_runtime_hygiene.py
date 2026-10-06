import tempfile
import unittest
from unittest.mock import patch
import collector
import journal
from journal import Journal
from session_view import session_page

class RuntimeHygieneTests(unittest.TestCase):
    def test_counter_paths_share_finite_nonnegative_projection(self):
        self.assertIs(collector.number, journal.number)
        for value in [None, True, False, -1, float('nan'), float('inf'), '100']:
            self.assertIsNone(collector.number(value))
        for value in [0, 3, 4.25]:
            self.assertEqual(collector.number(value), value)

    def test_labels_share_strict_sensitive_and_path_boundaries(self):
        self.assertIs(collector.safe_name, journal.safe_name)
        for value in ['PasswordReader', 'secretQuery', 'TOKEN_count', 'Bearer', 'sk-fixture',
                      'relative/path', '/absolute', 'https://example', 'a'*102, '', None]:
            self.assertEqual(collector.safe_name(value), 'other')
        for value in ['Read', 'mcp__example__read', 'namespace:tool', 'command.tests']:
            self.assertEqual(collector.safe_name(value), value)

    def test_chunk_digest_is_exact_old_canonical_digest_at_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(tmp)
            try:
                for count in [0, 1, 255, 256, 257, 512, 4097]:
                    rows=[{'id':i,'model':'пример','nested':[True, None, {'outcome':'unknown'}]} for i in range(count)]
                    self.assertEqual(j.digest_sequence('session-page-snapshot',rows),
                                     j.digest('session-page-snapshot',rows))
                # Same counters/IDs do not hide a changed field in an old call.
                before=[{'id':1,'received':1,'outcome':'unknown'}]
                after=[{'id':1,'received':1,'outcome':'success'}]
                self.assertNotEqual(j.digest_sequence('snapshot',before), j.digest_sequence('snapshot',after))
            finally:j.close()

    def test_cursor_created_with_previous_hash_algorithm_still_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(tmp)
            try:
                for i in range(3):
                    j.record('codex',{'hook_event_name':'PreToolUse','session_id':'demo',
                                     'tool_use_id':str(i),'tool_name':'Read'})
                sid=j.calls()[0]['session']
                with patch.object(j,'digest_sequence',side_effect=j.digest):
                    first=session_page(j,sid,limit=1)
                second=session_page(j,sid,first['nextCursor'],1)
                self.assertEqual(second['callCount'],3)
                self.assertEqual(second['pageOffset'],1)
                self.assertNotEqual(first['calls'][0]['id'],second['calls'][0]['id'])
            finally:j.close()
