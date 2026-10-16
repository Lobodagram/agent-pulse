import json
from pathlib import Path
import tempfile
import time
import unittest
from command_profile import profile, component_projection, component_evidence
from diagnostics import diagnostic_report
from journal import Journal
from analytics import findings


class CommandComponentsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.j=Journal(Path(self.tmp.name)/'state')

    def tearDown(self):
        self.j.close();self.tmp.cleanup()

    def event(self,command,call='one',phase='PreToolUse',tool='Bash'):
        raw={'hook_event_name':phase,'session_id':'s','turn_id':call,'tool_use_id':call,
             'tool_name':tool,'tool_input':{'command':command},'timestamp':time.time()-10,
             'commandComponents':{'operations':'PRIVATE_FAKE_NATIVE_EVIDENCE'}}
        if phase!='PreToolUse':raw['tool_response']={'exit_code':0}
        return self.j.record('glm',raw)

    def pair(self,command,call='one'):
        self.event(command,call);self.event(command,call,'PostToolUse')
        return next(c for c in self.j.calls() if c['id']==self.j.digest('call',['glm','s',call]))

    def test_partial_call_preserves_components_without_inventing_execution(self):
        self.pair('git status || PRIVATE_TOOL PRIVATE_ARGUMENT')
        c=self.j.calls()[0];e=c['commandComponents']
        self.assertEqual(c['operation'],'unknown')
        self.assertEqual(c['outcome'],'success')
        self.assertEqual(e['state'],'partial')
        self.assertEqual((e['recognized'],e['unknown'],e['total']),(1,1,2))
        self.assertEqual(e['operators'],['||'])
        self.assertFalse(e['executionVerified']);self.assertIsNone(e['outcomeAttribution'])
        self.assertNotIn('PRIVATE',json.dumps(e))

    def test_parts_never_inflate_call_or_outcome_coverage(self):
        for n,operator in enumerate([';','&&','|']):self.pair('cat PRIVATE '+operator+' PRIVATE_TOOL',str(n))
        diag=diagnostic_report(self.j,providers=['glm']);row=diag['commandCoverage'][0]
        self.assertEqual((row['calls'],row['classified'],row['unknown']),(3,0,3))
        parts=row['components']
        self.assertEqual(parts['partialCalls'],3)
        self.assertEqual(parts['recognizedInPartialCalls'],3)
        self.assertEqual(parts['partialFamilies'],{'read.cat':3})
        self.assertEqual(diag['calls'],3)

    def test_assignment_and_output_are_fixed_outer_families(self):
        for command in ["PRIVATE_VAR='PRIVATE value' ; printf '%s' PRIVATE ; echo PRIVATE ; git status",
                        r'PRIVATE_VAR=PRIVATE\ value ; ls PRIVATE']:
            p=profile(command)
            self.assertEqual(p['recognitionReason'],'classified')
            self.assertEqual(p['operations'][0],{'category':'environment','family':'shell-assignment'})
            self.assertNotIn('PRIVATE',json.dumps(p))
        self.assertEqual(profile('echo PRIVATE')['operations'][0]['family'],'shell-output')

    def test_quoted_command_looking_like_assignment_remains_unknown(self):
        for command in ["'PRIVATE=value' ; git status", "A=value 'PRIVATE=value' ; git status"]:
            p=profile(command)
            self.assertEqual(p['recognitionReason'],'partial-chain')
            self.assertEqual(p['operations'][0]['family'],'unknown')

    def test_opaque_or_unsupported_commands_never_supply_inner_parts(self):
        for command,expected in [("python3 - <<'PY'\nPRIVATE $(CODE)\npytest\nPY",'classified'),
                                 ('cat $(PRIVATE)','unparsed')]:
            self.pair(command,expected)
        calls={c['recognitionReason']:c for c in self.j.calls()}
        good=calls['classified']['commandComponents']
        self.assertEqual(good['operations'],[{'category':'run','family':'python-stdin'}])
        self.assertEqual(calls['shell-substitution']['commandComponents']['state'],'unparsed')
        self.assertNotIn('PRIVATE',json.dumps(self.j.calls()))

    def test_duplicate_and_legacy_delivery_never_backfill_parts(self):
        self.pair('git status ; PRIVATE_TOOL')
        self.j.db.execute('DELETE FROM command_components');self.j.db.commit()
        self.pair('echo PRIVATE ; git status')
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM command_components').fetchone()[0],0)
        c=self.j.calls()[0]
        self.assertIsNone(c['commandComponents']);self.assertEqual(c['operation'],'unknown')

    def test_missing_start_metadata_not_borrowed_from_finish(self):
        start=self.event('git status ; PRIVATE_TOOL')
        self.j.db.execute('DELETE FROM command_components WHERE event=?',(start,));self.j.db.commit()
        self.event('git status ; PRIVATE_TOOL',phase='PostToolUse')
        self.assertIsNone(self.j.calls()[0]['commandComponents'])
        self.event('git status ; PRIVATE_TOOL',call='missing-start',phase='PostToolUse')
        c=next(c for c in self.j.calls() if not c['paired'])
        self.assertEqual(c['commandComponents']['state'],'partial')
        self.assertEqual(c['collectionIssue'],'missing-start')

    def test_invalid_or_corrupted_components_are_unavailable(self):
        for value in ['PRIVATE','{}',json.dumps({'operations':[{'category':[],'family':'cat'}],'operators':[]}),
                      json.dumps({'operations':[{'category':'read','family':'PRIVATE'}],'operators':[]}),
                      json.dumps({'operations':[{'category':'read','family':'cat'}],'operators':['&&']})]:
            self.assertIsNone(component_evidence(value))
        self.pair('git status')
        self.j.db.execute("UPDATE command_components SET data='PRIVATE'");self.j.db.commit()
        row=diagnostic_report(self.j,providers=['glm'])['commandCoverage'][0]
        self.assertEqual(row['components']['notRecordedCalls'],1)
        self.assertEqual(row['components']['recordedCalls'],0)

    def test_non_shell_and_pruning_keep_side_table_scoped(self):
        self.event('PRIVATE',tool='Read')
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM command_components').fetchone()[0],0)
        self.pair('git status ; PRIVATE_TOOL')
        self.j.db.execute('UPDATE observation SET received=?',(time.time()-32*86400,));self.j.db.commit()
        self.j.prune()
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM command_components').fetchone()[0],0)
        self.assertEqual([r['name'] for r in self.j.db.execute('PRAGMA table_info(call_metadata)')],
                         ['event','signature','outcome_source'])

    def test_projection_privacy_at_bounded_chain_limit(self):
        command=' ; '.join(['cat PRIVATE']*31+['PRIVATE_TOOL PRIVATE'])
        e=component_evidence(json.dumps(component_projection(profile(command))))
        self.assertEqual((e['total'],e['recognized'],e['unknown']),(32,31,1))
        self.assertNotIn('PRIVATE',json.dumps(e))
        p=profile(command+' ; cat PRIVATE')
        self.assertEqual(p['recognitionReason'],'chain-parse-or-limit')
        self.assertEqual(p['operations'],[])

    def test_output_and_assignments_alone_do_not_create_automation_candidates(self):
        for n in range(12):self.pair('A=PRIVATE ; printf PRIVATE ; echo PRIVATE',str(n))
        calls=self.j.calls()
        self.assertEqual(len(calls),12)
        self.assertTrue(all(c['commandComponents']['state']=='classified' for c in calls))
        self.assertEqual(findings(self.j,calls),[])


if __name__=='__main__':unittest.main()
