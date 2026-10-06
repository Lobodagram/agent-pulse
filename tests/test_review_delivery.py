import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from journal import Journal
from analytics import report
from capability_detection import literal_reads, mcp_namespace
from finding_review import review_finding, reviewed_findings
from review_pack import markdown_pack
from scripts.workflow_check import handoff, archives
from mcp_server import dispatch

class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.j=Journal(self.root/'state');self.now=time.time();self.seq=0
    def tearDown(self):self.j.close();self.temp.cleanup()
    def pair(self,cmd='git status',at=None,turn='t',tool='Bash',response=None):
        self.seq+=1
        raw={'session_id':'s','turn_id':turn,'cwd':str(self.root),'tool_use_id':str(self.seq),'tool_name':tool,'tool_input':{'command':cmd},'timestamp':at or self.now-100}
        self.j.record('codex',dict(raw,hook_event_name='PreToolUse'))
        self.j.record('codex',dict(raw,hook_event_name='PostToolUse',timestamp=raw['timestamp']+1,tool_response={'exit_code':0} if response is None else response))
    def registry(self):
        self.j.import_inventory([{'provider':'codex','id':'fixture-check','kind':'skill','category':'test','status':'configured','locator':str(self.root/'skills/fixture-check/SKILL.md')}])
    def repeats(self,count,at):
        for n in range(count):self.pair(at=at+n*2,turn=str(n%3))
        return next(f['id'] for f in report(self.j)['findings'] if f['kind']=='repeat_call')
    def test_literal_readers_boundaries(self):
        for cmd in ["cat 'a b' && sed -n '1,12p' x",'head -n 20 a','tail -n5 a','/bin/cat -- a']:
            self.assertTrue(literal_reads('Bash',{'command':cmd}))
        for cmd in ['cat a; cat b','cat a || cat b','cat a | cat b','cat a > b','cat $A','cat $(x)','cat ~/a','cat a*','cat --help a','sed -n 10,2p a','sed -n 0p a','head -n -2 a','cat a && echo x','env cat a','cat a\ncat b','cat `x`']:
            self.assertEqual(literal_reads('Bash',{'command':cmd}),[],cmd)
        self.assertEqual(literal_reads('Read',{'command':'cat a'}),[])
    def test_registered_shell_load_not_invocation(self):
        self.registry();self.pair('cat skills/fixture-check/SKILL.md');cap=report(self.j)['capabilities'][0]
        self.assertEqual((cap['loaded'],cap['invoked']),(1,0));self.assertEqual(cap['evidenceSources'],{'shell-literal':1})
        self.pair('cat other/fixture-check/SKILL.md');self.assertEqual(report(self.j)['capabilities'][0]['loaded'],1)
    def test_failed_or_unknown_reader_not_loaded(self):
        self.registry()
        for response in [{'exit_code':1},{'session_id':42}]:self.pair('cat skills/fixture-check/SKILL.md',response=response)
        self.assertEqual(report(self.j)['capabilities'][0]['loaded'],0)
    def test_new_source_privacy_and_prune(self):
        self.registry();self.pair('cat skills/fixture-check/SKILL.md')
        for table in ['capability_source','capability_locator','capability_evidence']:
            for row in self.j.db.execute('SELECT * FROM '+table):self.assertNotIn(str(self.root),str(tuple(row)))
        self.j.db.execute('DELETE FROM observation');self.j.db.commit();self.j.prune()
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM capability_source').fetchone()[0],0)
    def test_namespace_identity_is_not_inventory_availability(self):
        for tool in ['mcp__files__read','functions.mcp__files__read']:
            self.assertEqual(mcp_namespace(tool),'files');self.pair(tool=tool)
        self.assertIsNone(mcp_namespace('mcp__bad space__x'))
        r=report(self.j);self.assertEqual(r['mcpNamespaces'][0]['calls'],2);self.assertFalse(r['mcpNamespaces'][0]['registered']);self.assertEqual(r['inventoryCount'],0)
    def test_generic_inventory_not_claimed_related(self):
        self.j.import_inventory([{'provider':'codex','id':'anything','kind':'skill','category':'shell','status':'configured'}]);self.repeats(6,self.now-200)
        self.assertEqual(report(self.j)['findings'][0]['inventoryStatus'],'no_match_in_inventory')
    def test_review_pending_and_invalid(self):
        fid=self.repeats(6,self.now-200);review_finding(self.j,fid,'actioned','script')
        r=reviewed_findings(self.j,self.j.calls())[0];self.assertEqual(r['recheckState'],'awaiting-window');self.assertIsNone(r['after']);self.assertFalse(r['causalClaim']);self.assertIsNone(r['tokenSavings'])
        for args in [('a'*32,'actioned','script',1),(fid,'bad','script',1),(fid,'open','payload',1),(fid,'open','script',True)]:
            with self.assertRaises(ValueError):review_finding(self.j,*args)
    def test_observational_lower_equal_windows(self):
        fid=self.repeats(12,self.now-200)
        review_finding(self.j,fid,'actioned','skill')
        # Recording timestamps in the future is intentionally avoided: move review clock back.
        self.j.db.execute('UPDATE finding_review SET at=?',(self.now-400,));self.j.db.commit()
        self.j.db.execute('DELETE FROM observation');self.j.db.execute('DELETE FROM call_metadata');self.j.db.commit()
        self.repeats(6,self.now-300)
        with patch('finding_review.time.time',return_value=self.now+86400):r=reviewed_findings(self.j,self.j.calls())[0]
        self.assertEqual(r['recheckState'],'observational-lower');self.assertEqual(r['baseline']['occurrences'],12);self.assertEqual(r['after']['occurrences'],6)
    def test_absence_not_zero_or_causal_resolution(self):
        fid=self.repeats(6,self.now-200);review_finding(self.j,fid,'actioned','fix')
        self.j.db.execute('UPDATE finding_review SET at=?',(self.now-86400,));self.j.db.execute('DELETE FROM observation');self.j.db.commit()
        for n in range(3):self.pair(cmd='git diff '+str(n),turn=str(n),at=self.now-300+n*2)
        r=reviewed_findings(self.j,self.j.calls())[0]
        self.assertEqual(r['recheckState'],'not-qualifying-in-observed-window');self.assertIsNone(r['after']['occurrences']);self.assertFalse(r['completeCoverage'])
        review_finding(self.j,fid,'dismissed');self.assertEqual(reviewed_findings(self.j,[])[0]['status'],'dismissed')
    def test_low_turns_insufficient_evidence(self):
        fid=self.repeats(6,self.now-200);review_finding(self.j,fid,'actioned')
        self.j.db.execute('UPDATE finding_review SET at=?',(self.now-86400,));self.j.db.execute('DELETE FROM observation');self.j.db.commit();self.pair(at=self.now-100)
        self.assertEqual(reviewed_findings(self.j,self.j.calls())[0]['recheckState'],'insufficient-evidence')
    def test_markdown_bilingual_and_read_only_mcp(self):
        self.pair('cat PRIVATE_SENTINEL')
        for language in ['en','ru']:
            r=dispatch({'method':'tools/call','params':{'name':'pulse_review_pack','arguments':{'language':language}}},self.root/'state')
            content=json.loads(r['content'][0]['text']);self.assertTrue(content['localOnly']);self.assertNotIn('PRIVATE_SENTINEL',content['markdown']);self.assertLess(len(content['markdown'].encode()),32769)
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM finding_review').fetchone()[0],0)
        with self.assertRaises(ValueError):markdown_pack(report(self.j),'bad')
    def test_cli_markdown_and_file_export(self):
        import subprocess,sys
        result=subprocess.run([sys.executable,'collector.py','--state',str(self.root/'state'),'journal','--format','markdown','--language','ru'],capture_output=True,text=True,check=True)
        self.assertTrue(result.stdout.startswith('# Agent Pulse'));self.assertIn('пакет проверки',result.stdout)
        dest=self.root/'report.md'
        result=subprocess.run([sys.executable,'collector.py','--state',str(self.root/'state'),'journal','--action','export','--format','markdown','--file',str(dest)],capture_output=True,text=True,check=True)
        self.assertTrue(json.loads(result.stdout)['saved']);self.assertTrue(dest.read_text().startswith('# Agent Pulse'))
    def test_provider_scoped_reviews(self):
        fid=self.repeats(6,self.now-200);review_finding(self.j,fid,'actioned')
        self.assertEqual(report(self.j,['glm'])['findingReviews'],[])
    def test_handoff_types_and_payload_exclusion(self):
        src={'schemaVersion':1,'version':'0.7.0','sourceCommit':'a'*40,'sourceDirty':True,'checks':{'sourceTreeSha256':'b'*64,'unitTests':'passed','unitTestCount':160,'publicFiles':90,'pythonSyntax':'passed','documentLinks':20,'privacyExport':'passed','raw':'private'}}
        self.assertNotIn('private',json.dumps(handoff(src)));self.assertTrue(handoff(src)['sourceDirty'])
        for key,value in [('unitTestCount',True),('unitTestCount','private'),('pythonSyntax','private')]:
            bad=json.loads(json.dumps(src));bad['checks'][key]=value
            with self.assertRaises(ValueError):handoff(bad)
        for key,value in [('version','private'),('sourceCommit','private'),('sourceDirty','private')]:
            bad=dict(src);bad[key]=value
            with self.assertRaises(ValueError):handoff(bad)
    def test_archive_hash_version_and_traversal(self):
        import hashlib,plistlib,zipfile
        names=['agent-pulse-macos-arm64.zip','agent-pulse-macos-x64.zip','agent-pulse-windows-x64.zip']
        def write(bad=False):
            for name in names:
                with zipfile.ZipFile(self.root/name,'w') as z:
                    z.writestr('pulse-runtime/x','fixture');z.writestr('LICENSE','MIT');z.writestr('NOTICE','fixture')
                    if 'macos-' in name:z.writestr('App.app/Contents/Info.plist',plistlib.dumps({'CFBundleShortVersionString':'0.7.0'}))
                    if bad:z.writestr('../escape','fixture')
            (self.root/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256((self.root/n).read_bytes()).hexdigest()+'  '+n for n in names))
        write();self.assertEqual(len(archives(self.root,'0.7.0')),3)
        with self.assertRaises(ValueError):archives(self.root,'0.6.1')
        (self.root/names[0]).write_bytes(b'bad')
        with self.assertRaises(ValueError):archives(self.root,'0.7.0')
        write(True)
        with self.assertRaises(ValueError):archives(self.root,'0.7.0')
