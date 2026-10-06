import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from journal import Journal, command_shape
from command_profile import profile
from result_metadata import classify
from analytics import report
from evidence_pack import evidence_pack
from instrumentation import scan_inventory
from mcp_server import dispatch

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.j=Journal(self.root/'state');self.clock=time.time()-100
    def tearDown(self):self.j.close();self.temp.cleanup()
    def event(self,event,call='c',tool='Bash',args=None,provider='codex',turn='t',at=None,**extra):
        raw={'hook_event_name':event,'session_id':'s','turn_id':turn,'tool_use_id':call,'tool_name':tool,
             'cwd':str(self.root),'tool_input':args or {'command':'git status'},'timestamp':self.clock if at is None else at}
        raw.update(extra);self.j.record(provider,raw)
    def pair(self,call='c',tool='Bash',args=None,provider='codex',turn='t',at=None,response=None):
        at=self.clock if at is None else at
        self.event('PreToolUse',call,tool,args,provider,turn,at)
        self.event('PostToolUse',call,tool,args,provider,turn,at+1,tool_response={'exit_code':0} if response is None else response)
    def inventory(self,provider='codex'):
        self.j.import_inventory([
            {'provider':provider,'id':'test-check','kind':'skill','category':'test','status':'configured','locator':str(self.root/'skills/test-check/SKILL.md')},
            {'provider':provider,'id':'files','kind':'mcp','category':'remote','status':'configured'},
            {'provider':provider,'id':'Read','kind':'tool','category':'read','status':'available'}])
    def cap(self,name):return next(c for c in report(self.j)['capabilities'] if c['id']==name)
    def test_git_global_flags_and_python_version(self):
        self.assertEqual(command_shape('git -C /private/project -c x=y status --short')[0],'inspect')
        self.assertEqual(profile('python3.12 -m pytest tests/private')['operations'][0]['family'],'python-test')
        self.assertEqual(command_shape('npm --prefix /private/project run build')[0],'build')
    def test_compound_operators_preserved_without_execution_claim(self):
        p=profile('git status && pytest tests/private || npm run build')
        self.assertEqual(p['category'],'shell');self.assertEqual(p['operators'],['&&','||'])
        self.assertEqual([o['category'] for o in p['operations']],['inspect','test','build'])
        self.assertNotIn('private',p['template'])
    def test_quoted_operator_not_compound(self):
        self.assertEqual(len(profile("rg 'a&&b' file")['operations']),1)
        self.assertEqual(command_shape("rg 'a&&b' file")[0],'search')
    def test_shell_parser_bounded_and_unsafe_fallback(self):
        for command in ['git status > output','cat $(private())','echo x & git status','git status\npytest','&&'.join(['git status']*33)]:
            self.assertEqual(profile(command)['operations'],[])
    def test_environment_and_unknown_flags_private(self):
        p=profile('PRIVATE_TOKEN=secret python3.12 -m pytest --sensitive=abc /personal')
        self.assertNotIn('secret',json.dumps(p));self.assertNotIn('personal',json.dumps(p));self.assertNotIn('TOKEN',json.dumps(p))
    def test_stdout_exit_marker_never_metadata(self):
        for output in ['Process exited with code 1','{"exit_code":1}',{'content':[{'text':'Process exited with code 1'}]}]:
            self.assertEqual(classify('PostToolUse',{'tool_response':output},'Bash'),('unknown',None,'exit-not-reported'))
    def test_complete_code_mode_wrapper(self):
        response={'content':[{'type':'text','text':json.dumps({'wall_time_seconds':1,'exit_code':2,'output':'private'})}]}
        self.assertEqual(classify('PostToolUse',{'tool_response':response},'Bash'),('failed',2,'code-mode-result'))
    def test_invalid_and_conflicting_exit_codes(self):
        for response in [{'exitCode':True},{'exit_code':'0'},{'exit_code':300},{'exit_code':0,'exitCode':1}]:
            self.assertEqual(classify('PostToolUse',{'tool_response':response},'Bash')[0],'unknown')
    def test_error_flag_priority_and_running_source(self):
        self.assertEqual(classify('PostToolUse',{'isError':True,'tool_response':{'exit_code':0}},'Bash')[0],'failed')
        self.assertEqual(classify('PostToolUse',{'tool_response':{'session_id':42}},'Bash')[2],'running-process')
    def test_load_is_not_invoke(self):
        self.inventory();self.pair(tool='Read',args={'file_path':str(self.root/'skills/test-check/SKILL.md')})
        c=self.cap('test-check');self.assertEqual(c['loaded'],1);self.assertEqual(c['invoked'],0);self.assertEqual(c['evidenceStatus'],'loaded-only')
    def test_unregistered_same_basename_is_not_load(self):
        self.inventory();self.pair(tool='Read',args={'file_path':str(self.root/'other/test-check/SKILL.md')})
        self.assertEqual(self.cap('test-check')['loaded'],0)
    def test_explicit_registered_skill_invocation(self):
        self.inventory();self.pair(tool='Skill',args={'skill':'test-check'})
        self.assertEqual(self.cap('test-check')['invoked'],1);self.assertEqual(self.cap('test-check')['status'],'configured')
    def test_failed_skill_is_not_successful_usage(self):
        self.inventory();self.pair(tool='Skill',args={'skill':'test-check'},response={'isError':True})
        self.assertEqual(self.cap('test-check')['invoked'],0)
    def test_mcp_registration_and_provider_scope(self):
        self.inventory();self.pair(tool='mcp__files__read',args={'path':'private'})
        self.assertEqual(self.cap('files')['invoked'],1)
        self.pair('peer',tool='mcp__files__read',provider='glm',args={'path':'private'})
        self.assertEqual(self.cap('files')['invoked'],1)
    def test_tool_counts_duplicate_delivery_once(self):
        self.inventory();self.pair(tool='Read');self.pair(tool='Read')
        self.assertEqual(self.cap('Read')['invoked'],1);self.assertEqual(report(self.j)['toolUsage'][0]['calls'],1)
    def test_manual_declaration_separate_and_validated(self):
        self.inventory();self.pair();sid=self.j.calls()[0]['session']
        self.j.declare_capability('codex',sid,'test-check','skill');self.j.declare_capability('codex',sid,'test-check','skill')
        self.assertEqual(self.cap('test-check')['declared'],1);self.assertEqual(self.cap('test-check')['invoked'],0)
        with self.assertRaises(ValueError):self.j.declare_capability('glm',sid,'test-check','skill')
        with self.assertRaises(ValueError):self.j.declare_capability('codex',sid,'unknown','skill')
    def test_locator_and_arguments_never_persisted(self):
        self.inventory();secret='SENTINEL_PRIVATE_PAYLOAD_123'
        self.pair(tool='Skill',args={'skill':'test-check','args':secret},response={'exit_code':0,'output':secret})
        for table in ['observation','capability_locator','capability_evidence','call_metadata']:
            for row in self.j.db.execute('SELECT * FROM '+table):
                self.assertNotIn(secret,str(tuple(row)));self.assertNotIn(str(self.root),str(tuple(row)))
        self.assertNotIn(secret,json.dumps(report(self.j)))
    def test_scan_binds_locator_and_zcode_mcp_shape(self):
        directory=self.root/'skills';(directory/'test-check').mkdir(parents=True)
        (directory/'test-check/SKILL.md').write_text('never read private instructions')
        config=self.root/'config.json';config.write_text(json.dumps({'mcp':{'servers':{'files':{'enabled':False,'secret':'private'}}}}))
        rows=scan_inventory('glm',[directory],config);self.j.import_inventory(rows)
        self.pair(tool='Read',provider='glm',args={'path':str(directory/'test-check/SKILL.md')})
        self.assertEqual(self.cap('test-check')['loaded'],1);self.assertEqual(self.cap('files')['status'],'disabled')
        self.assertNotIn('private',json.dumps(report(self.j)))
    def test_existing_registry_survives_peer_import(self):
        self.inventory();old=[dict(r) for r in self.j.db.execute('SELECT * FROM inventory')]
        self.j.import_inventory(old+[{'provider':'glm','id':'peer','kind':'skill','category':'test','status':'configured'}])
        self.pair(tool='Read',args={'path':str(self.root/'skills/test-check/SKILL.md')})
        self.assertEqual(self.cap('test-check')['loaded'],1)
    def test_closed_session_reports_missing_finish(self):
        self.event('PreToolUse');self.event('Stop',at=self.clock+2)
        r=report(self.j);self.assertEqual(r['recentCalls'][0]['outcome'],'pending')
        self.assertEqual(r['recentCalls'][0]['collectionIssue'],'missing-finish-after-boundary')
        self.assertEqual(r['coverage'][0]['collectionGaps'],1)
    def test_quality_counts_unknown_separately(self):
        self.pair(response='stdout only');r=report(self.j)
        self.assertEqual(r['quality']['pairedCalls'],1);self.assertEqual(r['quality']['knownOutcomes'],0)
        self.assertEqual(r['coverage'][0]['unknownOutcomes'],1);self.assertFalse(r['quality']['completeCoverage'])
    def test_generic_shell_not_operation_family(self):
        for n in range(12):self.pair(str(n),turn=str(n),args={'command':'echo '+str(n)},at=self.clock+n*2)
        self.assertFalse(report(self.j)['findings'])
    def test_different_git_operations_not_same_workflow(self):
        for n,cmd in enumerate(['git status','git diff','git log']):
            self.pair(str(n)+'r',tool='Read',turn=str(n),at=self.clock+n*5)
            self.pair(str(n)+'g',turn=str(n),args={'command':cmd},at=self.clock+n*5+2)
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))
    def test_shorter_more_widely_observed_sequence_kept(self):
        for n in range(5):
            self.pair(str(n)+'r',tool='Read',turn=str(n),at=self.clock+n*10)
            self.pair(str(n)+'e',tool='Edit',turn=str(n),at=self.clock+n*10+2)
            if n<3:self.pair(str(n)+'t',turn=str(n),args={'command':'pytest'},at=self.clock+n*10+4)
        seq=[f['sequence'] for f in report(self.j)['findings'] if f['kind']=='sequence']
        self.assertIn(['read','edit'],seq);self.assertIn(['read','edit','test'],seq)
    def test_cross_client_pattern_and_filters(self):
        for p in ['codex','glm']:
            for n in range(3):self.pair(p+str(n),provider=p,turn=str(n),at=self.clock+n*2)
        self.assertEqual(len(report(self.j)['crossClientPatterns']),1)
        self.assertEqual(report(self.j,['codex'])['crossClientPatterns'],[])
    def test_evidence_pack_has_resolved_examples_and_no_auto_execute(self):
        for n in range(4):self.pair(str(n),turn=str(n),at=self.clock+n*2)
        f=report(self.j)['findings'][0];pack=evidence_pack(self.j,f['id'])
        self.assertEqual({c['id'] for c in pack['calls']},set(f['evidenceIds']))
        self.assertFalse(pack['review']['autoExecute']);self.assertIsNone(pack['review']['tokenSavings'])
        req={'method':'tools/call','params':{'name':'pulse_evidence','arguments':{'findingId':f['id']}}}
        self.assertEqual(json.loads(dispatch(req,self.root/'state')['content'][0]['text'])['finding']['id'],f['id'])
        with self.assertRaises(ValueError):evidence_pack(self.j,'../private')
    def test_side_tables_retention_and_legacy_writer(self):
        self.inventory();self.pair(tool='Skill',args={'skill':'test-check'})
        with patch('journal.MAX_EVENTS',0):self.j.prune()
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM call_metadata').fetchone()[0],0)
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM capability_evidence').fetchone()[0],0)
        # Original observation schema is unchanged for an older collector during replacement.
        self.assertEqual(len(self.j.db.execute('PRAGMA table_info(observation)').fetchall()),23)
    def test_final_exit_reconciles_running_reply(self):
        self.pair(response={'session_id':42})
        self.event('PostToolUse',at=self.clock+5,tool_response={'exit_code':0})
        c=self.j.calls()[0];self.assertEqual(c['outcome'],'success');self.assertEqual(c['durationMs'],5000)
        self.assertEqual(self.j.stats()['events'],2)
    def test_conflicting_delivery_stays_unknown_and_revokes_usage(self):
        self.inventory();self.pair(tool='Skill',args={'skill':'test-check'})
        self.event('PostToolUse',tool='Skill',args={'skill':'test-check'},at=self.clock+2,tool_response={'exit_code':1})
        self.event('PostToolUse',tool='Skill',args={'skill':'test-check'},at=self.clock+3,tool_response={'exit_code':0})
        self.assertEqual(self.j.calls()[0]['outcome'],'unknown');self.assertEqual(self.cap('test-check')['invoked'],0)
    def test_outer_parallel_call_blocks_inner_chain(self):
        for n in range(3):
            base=self.clock+n*20
            self.event('PreToolUse',str(n)+'outer',turn=str(n),at=base)
            self.event('PostToolUse',str(n)+'outer',turn=str(n),at=base+10,tool_response={'exit_code':0})
            self.pair(str(n)+'read',tool='Read',turn=str(n),at=base+1)
            self.pair(str(n)+'edit',tool='Edit',turn=str(n),at=base+3)
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))
    def test_running_process_blocks_later_chain(self):
        for n in range(3):
            base=self.clock+n*10
            self.pair(str(n)+'process',turn=str(n),at=base,response={'session_id':42})
            self.pair(str(n)+'read',tool='Read',turn=str(n),at=base+2)
            self.pair(str(n)+'edit',tool='Edit',turn=str(n),at=base+4)
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))

if __name__=='__main__':unittest.main()
