import base64
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
from journal import Journal
from journal_cli import run
from mcp_server import dispatch
from session_view import session_page

class SessionPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.j=Journal(self.tmp.name);self.at=time.time()-100
        for i in range(12):self.pair(str(i),self.at+i)
        self.sid=self.j.calls()[0]['session']
    def tearDown(self):self.j.close();self.tmp.cleanup()
    def pair(self,call,at):
        raw={'session_id':'page-demo','turn_id':'turn-demo','tool_use_id':call,'tool_name':'Read','tool_input':{},'timestamp':at,'model':'demo-model'}
        self.j.record('codex',dict(raw,hook_event_name='PreToolUse'))
        self.j.record('codex',dict(raw,hook_event_name='PostToolUse',timestamp=at+.1))
    def test_pages_exhaust_all_calls_once(self):
        ids=[];cursor=None;times=[];offsets=[]
        while True:
            page=session_page(self.j,self.sid,cursor,5)
            ids.extend(c['id'] for c in page['calls']);times.append(page['snapshotAt']);offsets.append(page['pageOffset'])
            self.assertEqual(page['callCount'],12);cursor=page['nextCursor']
            if cursor is None:break
        self.assertEqual(len(set(ids)),12);self.assertEqual(len(ids),12)
        self.assertEqual(offsets,[0,5,10]);self.assertEqual(len(set(times)),1)
    def test_new_backdated_event_does_not_shift_pages_or_first_page(self):
        first=session_page(self.j,self.sid,limit=5)
        self.pair('late',self.at-1)
        second=session_page(self.j,self.sid,first['nextCursor'],5)
        replay=session_page(self.j,self.sid,first['cursor'],5)
        self.assertEqual(second['callCount'],12);self.assertEqual(replay['calls'],first['calls'])
        self.assertFalse({c['id'] for c in first['calls']} & {c['id'] for c in second['calls']})
        self.assertEqual(session_page(self.j,self.sid)['callCount'],13)
    def test_cursor_rejects_tamper_other_session_and_invalid_limits(self):
        first=session_page(self.j,self.sid,limit=5)
        raw=json.loads(base64.urlsafe_b64decode(first['nextCursor']))
        raw[1]=6;bad=base64.urlsafe_b64encode(json.dumps(raw).encode()).decode()
        for cursor in [bad,'@@bad',False,'x'*513]:
            with self.assertRaises(ValueError):session_page(self.j,self.sid,cursor)
        with self.assertRaises(ValueError):session_page(self.j,'a'*32,first['nextCursor'])
        for limit in [True,0,501,1.2,'5']:
            with self.assertRaises(ValueError):session_page(self.j,self.sid,limit=limit)
    def test_cli_page_file_and_mcp_continuation(self):
        destination=Path(self.tmp.name)/'page.json'
        args=SimpleNamespace(state=Path(self.tmp.name),action='session',session=self.sid,cursor=None,limit=5,file=destination)
        saved=run(args);self.assertTrue(saved['saved']);self.assertEqual(len(json.loads(destination.read_text())['calls']),5)
        req={'method':'tools/call','params':{'name':'pulse_session','arguments':{'sessionId':self.sid,'limit':5,'cursor':saved['nextCursor']}}}
        page=json.loads(dispatch(req,Path(self.tmp.name))['content'][0]['text'])
        self.assertEqual(page['pageOffset'],5);self.assertEqual(page['callCount'],12)
    def test_empty_session_and_mcp_limits(self):
        empty=session_page(self.j,'a'*32)
        self.assertEqual(empty['calls'],[]);self.assertIsNone(empty['nextCursor']);self.assertEqual(empty['callCount'],0)
        for limit in [True,101]:
            req={'method':'tools/call','params':{'name':'pulse_session','arguments':{'sessionId':self.sid,'limit':limit}}}
            with self.assertRaises(ValueError):dispatch(req,Path(self.tmp.name))
    def test_reconciliation_invalidates_old_cursor(self):
        first=session_page(self.j,self.sid,limit=5)
        self.j.record('codex',{'session_id':'page-demo','turn_id':'turn-demo','tool_use_id':'0','tool_name':'Read','tool_input':{},'timestamp':self.at,'model':'different-model','hook_event_name':'PreToolUse'})
        with self.assertRaisesRegex(ValueError,'snapshot_changed'):session_page(self.j,self.sid,first['nextCursor'],5)
    def test_coarse_clock_new_events_never_enter_old_pages(self):
        with patch('journal.time.time',return_value=time.time()):
            first=session_page(self.j,self.sid,limit=5)
            self.pair('same-clock-tick',self.at-1)
            second=session_page(self.j,self.sid,first['nextCursor'],5)
            replay=session_page(self.j,self.sid,first['cursor'],5)
            self.assertEqual(second['callCount'],12);self.assertEqual(replay['calls'],first['calls'])
            self.assertEqual(session_page(self.j,self.sid)['callCount'],13)
