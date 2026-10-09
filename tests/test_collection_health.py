"""Explicit helper/store boundaries; all events use temporary invented state."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from journal import Journal
from check_receipts import receipt,check_report,Reporter
from collection_health import health,backup

class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.j=Journal(self.root/'state');self.start=time.time()-10
        self.spec=dict(runId='a'*32,provider='codex',operation='workflow-check',version='1.0.0',startedAt=self.start,status='started')
    def tearDown(self):self.j.close();self.tmp.cleanup()
    def end(self,**kwargs):return dict(self.spec,status='success',endedAt=self.start+1,gates={'unit-tests':'passed'},**kwargs)
    def test_receipt_dedup_and_native_outcome_separation(self):
        receipt(self.j,self.spec);receipt(self.j,self.end());receipt(self.j,self.end());receipt(self.j,self.spec)
        r=check_report(self.j)
        self.assertEqual((r['runs'],r['knownResults'],r['startsObserved']),(1,1,1));self.assertEqual(r['knownResultRate'],1)
        self.assertEqual(r['recent'][0]['elapsedMs'],1000);self.assertEqual(r['nativeOutcomesChanged'],0)
        self.assertIsNone(r['humanAcceptance']);self.assertEqual(self.j.calls(),[])
    def test_conflicting_receipts_stay_unknown(self):
        receipt(self.j,self.spec);receipt(self.j,self.end());bad=self.end();bad.update(status='failed',gates={'unit-tests':'failed'})
        receipt(self.j,bad);receipt(self.j,self.end());r=check_report(self.j)
        self.assertEqual(r['knownResults'],0);self.assertEqual(r['conflicts'],1);self.assertIsNone(r['recent'][0]['elapsedMs'])
    def test_invalid_payloads_and_identity_rejected(self):
        for extra in ({'command':'PRIVATE_CANARY'}, {'gates':{'prompt':'passed'}}, {'startedAt':True}, {'endedAt':float('inf')}, {'provider':[]}, {'version':'private phrase'}):
            s=self.end();s.update(extra)
            with self.subTest(extra=extra),self.assertRaises(ValueError):receipt(self.j,s)
        receipt(self.j,self.spec);s=self.end();s['operation']='ci-summary'
        with self.assertRaises(ValueError):receipt(self.j,s)
        self.assertNotIn('PRIVATE_CANARY',json.dumps(check_report(self.j)))
    def test_pending_stale_and_provider_filter(self):
        self.spec['startedAt']=time.time()-1000;receipt(self.j,self.spec)
        self.assertEqual(check_report(self.j)['staleRuns'],1);self.assertEqual(check_report(self.j,{'glm'})['runs'],0)
        self.assertIsNone(check_report(self.j,{'glm'})['knownResultRate'])
    def test_missing_start_is_reported_not_hidden(self):
        receipt(self.j,self.end());r=check_report(self.j);self.assertEqual(r['finishWithoutStart'],1);self.assertEqual(r['startsObserved'],0)
    def test_prune_counters_start_now_and_dont_double_count(self):
        receipt(self.j,self.spec);self.j.db.execute('UPDATE check_run SET started=?',(time.time()-31*86400,));self.j.db.commit()
        self.j.prune();self.j.prune();r=health(self.j)
        self.assertEqual(r['integrity'],'ok');self.assertEqual(r['retentionCounters']['expired-checks']['count'],1)
        self.assertGreater(r['retentionCounters']['expired-checks']['supportedSince'],self.start)
    def test_reporter_failure_does_not_mask_helper_result(self):
        with patch('check_receipts.receipt',side_effect=ValueError('PRIVATE_CANARY')):
            r=Reporter(self.root/'broken','codex','workflow-check','v1');self.assertFalse(r.finish('failed'))
    def test_verified_backup_is_exclusive_private_and_has_no_keys(self):
        receipt(self.j,self.spec);key=json.loads((self.j.state/'Secrets.json').read_text())['journalHmacKey']
        dest=self.root/'backups'/'journal.sqlite';r=backup(self.j,dest)
        self.assertEqual(r['integrity'],'ok');self.assertFalse(r['includesCredentials'])
        self.assertNotIn(key.encode(),dest.read_bytes())
        if os.name!='nt':self.assertEqual(dest.stat().st_mode&0o777,0o600)
        with sqlite3.connect(dest) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM check_run').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT fingerprint FROM backup_identity').fetchone()[0],self.j.digest('backup-key',['journal']))
        with self.assertRaises(ValueError):backup(self.j,dest)
        self.assertFalse(list(dest.parent.glob('.pulse-backup-*')))
    def test_backup_publication_race_never_overwrites(self):
        dest=self.root/'backups'/'journal.sqlite'
        def race(src,dst):Path(dst).write_bytes(b'keep');raise FileExistsError()
        with patch('collection_health.os.link',side_effect=race),self.assertRaises(FileExistsError):backup(self.j,dest)
        self.assertEqual(dest.read_bytes(),b'keep');self.assertFalse(list(dest.parent.glob('.pulse-backup-*')))
    def test_receipt_write_is_atomic(self):
        receipt(self.j,self.spec)
        self.j.db.execute("CREATE TRIGGER reject_finish BEFORE UPDATE ON check_run BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError):receipt(self.j,self.end())
        self.assertEqual(check_report(self.j)['recent'][0]['status'],'started')
    def test_readonly_mcp_health_and_receipts(self):
        from mcp_server import dispatch
        for name in ('pulse_collection_health','pulse_check_receipts'):
            value=dispatch({'method':'tools/call','params':{'name':name,'arguments':{}}},self.j.state)
            self.assertFalse(value['isError'])
        names={t['name'] for t in dispatch({'method':'tools/list'},self.j.state)['tools']}
        self.assertNotIn('pulse_backup_journal',names)

    def test_control_import_and_backup_require_explicit_enablement(self):
        from mcp_server import dispatch
        request={'method':'tools/call','params':{'name':'pulse_record_check','arguments':self.spec}}
        with self.assertRaises(ValueError):dispatch(request,self.j.state)
        self.assertFalse(dispatch(request,self.j.state,allow_control=True)['isError'])
        request['params']={'name':'pulse_backup_journal','arguments':{'destination':str(self.root/'backup'/'saved.sqlite')}}
        with self.assertRaises(ValueError):dispatch(request,self.j.state)
        self.assertFalse(dispatch(request,self.j.state,allow_control=True)['isError'])

    def test_no_retained_records_do_not_become_zero_percent_coverage(self):
        self.assertIsNone(check_report(self.j)['knownResultRate'])
        self.assertIsNone(check_report(self.j)['humanAcceptance'])

    def test_analysis_cap_and_discard_counters_are_separate(self):
        raw={'session_id':'demo','turn_id':'one','tool_use_id':'call','tool_name':'Read','timestamp':time.time()}
        for event in ['PreToolUse','PostToolUse']:self.j.record('codex',dict(raw,hook_event_name=event))
        with patch('journal.MAX_EVENTS',1):self.j.prune()
        h=health(self.j);self.assertEqual(h['retentionCounters']['capped-events']['count'],1)
        self.assertFalse(h['analysisLimitReached'])
        self.assertEqual(h['retentionCounters']['expired-events']['count'],0)

    def test_analysis_retains_earlier_evidence_beyond_twenty_thousand_events(self):
        from session_view import session_page
        raw={'session_id':'demo','turn_id':'one','tool_use_id':'original','tool_name':'Read','timestamp':time.time()-100}
        for event in ['PreToolUse','PostToolUse']:self.j.record('codex',dict(raw,hook_event_name=event))
        original=self.j.digest('call',['codex','demo','original'])
        row=list(self.j.db.execute("SELECT * FROM observation WHERE phase='finish'").fetchone())
        rows=[]
        for i in range(20005):
            value=list(row);value[0]=f'{i:032x}';value[6]=f'{i:032x}';value[9]=time.time()-50
            rows.append(value)
        self.j.db.executemany('INSERT INTO observation VALUES ('+','.join('?' for _ in row)+')',rows);self.j.db.commit()
        calls=self.j.calls();self.assertEqual(len(calls),20006)
        self.assertIn(original,{c['id'] for c in calls})
        self.assertEqual(health(self.j)['analysisEventLimit'],100000)
        self.assertFalse(health(self.j)['analysisLimitReached'])
        session=self.j.digest('session',['codex','demo']);page=session_page(self.j,session,limit=1)
        self.assertEqual(page['callCount'],20006);self.assertFalse(page['eventLimitReached'])
    def test_failed_tests_emit_failed_receipt(self):
        from scripts import workflow_check as workflow
        output=self.root/'result.json'
        with patch('sys.argv',['workflow_check','check','--output',str(output),'--pulse-state',str(self.j.state),'--pulse-provider','codex']),patch.object(workflow,'source_check',return_value=('1.0.0',{'sourceTreeSha256':'f'*64,'unitTests':'failed','pythonSyntax':'passed','privacyExport':'passed','documentLinks':1})),patch('builtins.print'):
            self.assertEqual(workflow.main(),1)
        self.assertEqual(check_report(self.j)['recent'][0]['status'],'failed')
