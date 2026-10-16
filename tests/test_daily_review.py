from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from daily_review import daily_review, daily_markdown, day_bounds, quota_summary, metrics_summary
from journal import Journal
from mcp_server import dispatch


class DailyReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / 'state'
        self.j = Journal(self.state)
        self.day = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        self.start, self.end = day_bounds(self.day, 120)

    def tearDown(self):
        self.j.close()
        self.tmp.cleanup()

    def pair(self, n, tool='Bash', response=None, at=None):
        raw = {'session_id': 'demo', 'turn_id': str(n), 'tool_use_id': str(n),
               'tool_name': tool, 'tool_input': {'command': 'PRIVATE_COMMAND', 'code': 'PRIVATE_CODE'},
               'timestamp': self.start + 100 + n if at is None else at}
        self.j.record('glm', dict(raw, hook_event_name='PreToolUse'))
        self.j.record('glm', dict(raw, hook_event_name='PostToolUse', timestamp=raw['timestamp'] + .1,
                                  tool_response=response if response is not None else {'exit_code': 0}))

    def sample(self, remaining, stamp, reset='future', scope=None, bucket='glm'):
        if reset == 'future':
            reset = self.end + 100
        return (stamp, {'status': 'ready', 'quotaStatus': 'ready', 'accountScope': scope,
                        'quotaObservedAt': stamp, 'quotas': [{'bucket': bucket, 'kind': 'secondary', 'durationMinutes': 10080,
                                                            'remainingPercent': remaining, 'resetsAt': reset}]})

    def test_full_day_counts_do_not_sum_truncated_diagnostic_groups(self):
        self.pair(-1, at=self.start-1)
        for n in range(125):
            self.pair(n, tool='DemoTool'+str(n))
        self.pair(1000, at=self.end)
        row = daily_review(self.j, self.day, 120, 'glm')['providers'][0]
        self.assertEqual(row['calls'], 125)
        self.assertEqual(row['knownPairedOutcomes'], 125)
        self.assertEqual(sum(row['tools'].values()), 125)
        self.assertNotIn('PRIVATE_', json.dumps(row))

    def test_unknown_shell_and_failure_guidance_preserve_unknowns(self):
        self.pair(1, response={'output': 'PRIVATE_STDOUT without exit'})
        self.pair(2, tool='mcp__node_repl__js', response={'isError': True, 'error': {'code': 'MODULE_NOT_FOUND', 'message': 'PRIVATE_STACK'}})
        self.pair(3, tool='mcp__node_repl__js', response={'isError': True, 'content': [{'text': 'PRIVATE_STACK'}]})
        result = daily_review(self.j, self.day, 120, 'glm')
        row = result['providers'][0]
        self.assertEqual(row['outcomes'], {'unknown': 1, 'failed': 2})
        self.assertEqual(row['knownPairedOutcomes'], 2)
        self.assertEqual(row['failures'][0]['failureClasses'], {'module-not-found': 1, 'unknown': 1})
        self.assertTrue(all(not s['autoRetry'] for s in row['failures'][0]['nextSteps']))
        self.assertFalse(row['failures'][0]['sameCauseConfirmed'])
        self.assertNotIn('PRIVATE_', json.dumps(result))
        self.assertIn('Причинная экономия подписки: не измерена', daily_markdown(result, 'ru'))

    def test_weekly_delta_and_primary_resets_are_different(self):
        rows = [self.sample(79, self.start+100), self.sample(73, self.end-100)]
        quota = quota_summary(rows, self.start, self.end)
        self.assertEqual(quota['windows'][0]['consumedPercentagePoints'], 6)
        rows[1][1]['quotas'][0]['resetsAt'] += 100
        self.assertIsNone(quota_summary(rows, self.start, self.end)['windows'][0]['consumedPercentagePoints'])
        self.assertIsNone(quota['completeDayConsumption'])

    def test_unknown_reset_correction_account_switch_and_cap_disable_delta(self):
        for reset, remain, scope, capped in [(None, 73, None, False), ('future', 80, None, False),
                                             ('future', 73, 'changed-scope', False), ('future', 73, None, True),
                                             (self.start-100, 73, None, False)]:
            rows = [self.sample(79, self.start+100, reset, 'first-scope'),
                    self.sample(remain, self.end-100, reset, scope)]
            self.assertIsNone(quota_summary(rows, self.start, self.end, capped)['windows'][0]['consumedPercentagePoints'])

    def test_stale_cached_invalid_and_distinct_account_buckets(self):
        stale = self.sample(73, self.end-100)
        stale[1]['quotaObservedAt'] = self.start-1
        cached = self.sample(73, self.end-100)
        cached[1]['sourceStatus'] = ['cached_previous_read']
        self.assertEqual(quota_summary([stale, cached], self.start, self.end)['windows'], [])
        rows = [self.sample(79, self.start+100, bucket='codex'), self.sample(73, self.end-100, bucket='other-product')]
        for _, payload in rows:
            payload.pop('quotaStatus')  # Codex uses status + explicit quotaObservedAt.
        windows = quota_summary(rows, self.start, self.end)['windows']
        self.assertEqual(len(windows), 2)
        self.assertTrue(all(w['consumedPercentagePoints'] is None for w in windows))

    def test_missing_metrics_does_not_create_file_and_tokens_remain_separate(self):
        review = daily_review(self.j, self.day, 120, 'glm')
        self.assertFalse((self.state/'metrics.sqlite').exists())
        self.assertIsNone(review['providers'][0]['usageUTC']['tokens'])
        db = sqlite3.connect(self.state/'metrics.sqlite')
        db.executescript('CREATE TABLE samples(provider,at,data); CREATE TABLE daily(provider,date,tokens,source);')
        for stamp, payload in [self.sample(79, self.start+100), self.sample(73, self.end-100)]:
            db.execute('INSERT INTO samples VALUES (?,?,?)', ('glm', stamp, json.dumps(payload)))
        db.execute('INSERT INTO daily VALUES (?,?,?,?)', ('glm', self.day, 108105550, 'ZCode usage/stats'))
        db.commit(); db.close()
        r = daily_review(self.j, self.day, 120, 'glm')
        row = r['providers'][0]
        self.assertEqual(row['quota']['windows'][0]['consumedPercentagePoints'], 6)
        self.assertEqual(row['usageUTC']['tokens'], 108105550)
        self.assertIsNone(row['usageUTC']['billingCost'])
        self.assertIn('Отдельный день UTC', daily_markdown(r, 'ru'))

    def test_pending_calls_and_local_scope_do_not_become_task_acceptance(self):
        self.j.record('glm', {'session_id': 'demo', 'turn_id': 'one', 'tool_use_id': 'one',
                            'tool_name': 'Read', 'timestamp': self.start+100, 'hook_event_name': 'PreToolUse'})
        row = daily_review(self.j, self.day, 120, 'glm')['providers'][0]
        self.assertEqual(row['outcomes'], {'pending': 1})
        self.assertIsNone(row['failureRateAmongKnown'])
        self.assertEqual(row['reviewsRecordedOnDay'], {})
        self.assertIsNone(row['helperReceipts']['humanAcceptance'])

    def test_read_only_mcp_and_validation(self):
        self.pair(1)
        request = {'method': 'tools/call', 'params': {'name': 'pulse_daily_review',
                   'arguments': {'date': self.day, 'utcOffsetMinutes': 120, 'provider': 'glm', 'language': 'ru'}}}
        before = self.j.db.execute('SELECT count(*) FROM observation').fetchone()[0]
        result = dispatch(request, self.state)
        self.assertIn('дневная сводка', json.loads(result['content'][0]['text'])['markdown'])
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM observation').fetchone()[0], before)
        for day, offset, provider in [('2026-02-30', 120, 'glm'), (self.day, True, 'glm'),
                                     (self.day, 841, 'glm'), (self.day, 120, 'PRIVATE_PROVIDER')]:
            with self.assertRaises(ValueError):
                daily_review(self.j, day, offset, provider)
        with self.assertRaises(ValueError):
            daily_markdown(daily_review(self.j, self.day, 120), 'PRIVATE_LANGUAGE')

    def test_symlink_metrics_rejected(self):
        target = Path(self.tmp.name)/'not-pulse.sqlite'
        target.write_bytes(b'private')
        (self.state/'metrics.sqlite').symlink_to(target)
        with self.assertRaises(ValueError):
            metrics_summary(self.state, 'glm', self.day, self.start, self.end)
