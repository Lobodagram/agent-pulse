from pathlib import Path
import json
import tempfile
import time
import unittest
from command_profile import profile
from capability_detection import literal_reads
from diagnostics import diagnostic_report
from journal import Journal
from analytics import report
from review_pack import markdown_pack


class CommandProjectionTests(unittest.TestCase):
    def families(self, command):
        return [o['category']+'.'+o['family'] for o in profile(command)['operations']]

    def test_outer_script_invocations_do_not_claim_script_purpose(self):
        cases={"python3.12 -c 'print(\"PRIVATE\")'":['run.python-inline'],
               'python3 /PRIVATE/check_tests.py':['run.python-script'],
               'python3 -m PRIVATE':['run.python-module'],
               "node -e 'PRIVATE'":['run.node-inline'],
               'bash -lc "pytest PRIVATE"':['run.shell-inline']}
        for cmd,expected in cases.items():
            with self.subTest(cmd=cmd):
                self.assertEqual(self.families(cmd),expected)
                self.assertNotIn('PRIVATE',json.dumps(profile(cmd)))

    def test_heredoc_body_is_opaque_even_with_fake_tools_and_secrets(self):
        cmd="cd /PRIVATE && python3 - <<'PY'\npytest PRIVATE\ngit push $(PRIVATE)\n`PRIVATE`\nPY\n"
        self.assertEqual(self.families(cmd),['environment.cd','run.python-stdin'])
        text=json.dumps(profile(cmd));self.assertNotIn('PRIVATE',text);self.assertNotIn('pytest',text)
        self.assertEqual(self.families('node - <<-JS\n\tPRIVATE\n\tJS'),['run.node-stdin'])

    def test_invalid_and_nonterminal_heredoc_stays_unknown(self):
        for cmd in ['python3 - <<PY\nPRIVATE','python3 - <<PY\nPRIVATE\nPY\npytest',
                    'cat <<< PRIVATE','python3 - <<$PRIVATE\nbody\nPRIVATE',
                    'python3 - <<PY <<OTHER\nbody\nPY']:
            self.assertEqual(profile(cmd)['operations'],[],cmd)

    def test_newline_and_redirection_projection_without_read_evidence(self):
        cmd='cd /PRIVATE\npython3 -m pytest > "/PRIVATE/result file" 2>&1\ngit status'
        self.assertEqual(self.families(cmd),['environment.cd','test.python-test','inspect.git-status'])
        self.assertNotIn('PRIVATE',json.dumps(profile(cmd)))
        for cmd in ['cat a > b','cat a\ncat b',"cat <<'PY'\na\nPY",'env cat a','cat a | head']:
            self.assertEqual(literal_reads('Bash',{'command':cmd}),[])

    def test_quoted_operators_are_arguments_not_commands(self):
        self.assertEqual(self.families("rg 'x > y; z' PRIVATE"),['search.rg'])
        self.assertEqual(self.families("python3 -c 'PRIVATE; pytest > x'"),['run.python-inline'])

    def test_known_checks_and_file_operations_are_private(self):
        for cmd,expected in [('env PRIVATE_TOKEN=PRIVATE timeout 2s python3 -m unittest','test.python-test'),
                             ('npm --prefix /PRIVATE run lint','inspect.npm-lint'),
                             ('pnpm -C /PRIVATE run dev','run.pnpm-dev'),
                             ('git -C /PRIVATE add PRIVATE','edit.git-add'),
                             ('mkdir -p /PRIVATE','edit.files-mkdir'),
                             ('find /PRIVATE -name PRIVATE','search.find'),
                             ('npx eslint PRIVATE','inspect.node-eslint'),
                             ('python3 --version','environment.python3')]:
            self.assertEqual(self.families(cmd),[expected]);self.assertNotIn('PRIVATE',json.dumps(profile(cmd)))

    def test_substitution_background_and_missing_redirect_target_are_unknown(self):
        for cmd in ['cat $(PRIVATE)','git status >$(PRIVATE)','cat <(PRIVATE)',
                    'git status & pytest','git status >','git status >>> PRIVATE',
                    '&&'.join(['git status']*33),'python3 '+'x'*32769]:
            self.assertEqual(profile(cmd)['operations'],[],cmd)


class SkillObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.j=Journal(self.root/'state');self.n=0
        self.path=self.root/'shared/fixture-check/SKILL.md'
        self.j.import_inventory([{'provider':'codex','id':'fixture-check','kind':'skill',
                                 'category':'test','status':'configured','locator':str(self.path)},
                                {'provider':'codex','id':'files','kind':'mcp','category':'remote','status':'configured'}])

    def tearDown(self):self.j.close();self.tmp.cleanup()

    def pair(self,tool,args,response=None):
        self.n+=1;now=time.time()-100
        raw={'session_id':'s','turn_id':str(self.n),'tool_use_id':str(self.n),'tool_name':tool,
             'tool_input':args,'cwd':str(self.root),'timestamp':now}
        self.j.record('glm',dict(raw,hook_event_name='PreToolUse'))
        self.j.record('glm',dict(raw,hook_event_name='PostToolUse',timestamp=now+1,
                                tool_response={} if response is None else response))

    def coverage(self):return diagnostic_report(self.j,providers=['glm'])['skillEvidenceCoverage'][0]

    def test_peer_catalog_exact_read_is_loaded_only_under_actual_client(self):
        self.pair('Read',{'file_path':str(self.path)})
        rows=report(self.j)['capabilities'];peer=next(r for r in rows if r['provider']=='glm')
        self.assertEqual((peer['loaded'],peer['invoked']),(1,0))
        self.assertEqual(peer['status'],'not-in-current-inventory')
        self.assertEqual(peer['evidenceSources'],{'shared-catalog-read-tool':1})
        self.assertEqual(next(r for r in rows if r['provider']=='codex' and r['kind']=='skill')['loaded'],0)
        self.assertEqual(self.coverage()['skillReadCalls'],1);self.assertFalse(self.coverage()['versionVerified'])

    def test_successful_native_skill_matches_reviewed_shared_identity(self):
        self.pair('Skill',{'skill':'fixture-check','args':'PRIVATE_BODY'})
        row=self.coverage();self.assertEqual((row['mappedSkillToolCalls'],row['skillReadCalls']),(1,0))
        self.assertFalse(row['nonUseEstablished'])
        self.assertEqual(self.j.calls()[0]['operation'],'skill.invoke')

    def test_unknown_skill_is_counted_without_retaining_its_private_name(self):
        self.pair('Skill',{'skill':'PRIVATE_UNKNOWN','args':'PRIVATE_BODY'})
        row=self.coverage();self.assertEqual(row['unmappedSuccessfulSkillToolCalls'],1)
        self.assertEqual(row['mappedSkillToolCalls'],0);self.assertFalse(row['nonUseEstablished'])
        self.assertNotIn('PRIVATE_',json.dumps(report(self.j)))

    def test_same_basename_and_failed_read_are_not_loaded(self):
        self.pair('Read',{'file_path':str(self.root/'other/fixture-check/SKILL.md')})
        self.pair('Read',{'file_path':str(self.path)},{'isError':True})
        self.assertEqual(self.coverage()['skillReadCalls'],0)

    def test_peer_mcp_configuration_never_establishes_glm_invocation(self):
        self.pair('mcp__files__read',{})
        self.assertFalse(any(r['provider']=='glm' for r in report(self.j)['capabilities']))

    def test_conflicting_finish_revokes_shared_skill_evidence(self):
        self.pair('Skill',{'skill':'fixture-check'})
        self.j.record('glm',{'hook_event_name':'PostToolUse','session_id':'s','turn_id':'1',
                            'tool_use_id':'1','tool_name':'Skill','tool_input':{'skill':'fixture-check'},
                            'timestamp':time.time()-90,'tool_response':{'isError':True}})
        self.assertEqual(self.coverage()['mappedSkillToolCalls'],0)
        self.assertEqual(self.j.db.execute("SELECT count(*) FROM capability_evidence WHERE provider='glm'").fetchone()[0],0)

    def test_command_coverage_keeps_unknown_and_native_outcome_separate(self):
        self.pair('Bash',{'command':'python3 - <<PY\nPRIVATE_BODY\nPY'},{'exit_code':0})
        self.pair('Bash',{'command':'PRIVATE_COMMAND PRIVATE_BODY'},{'exit_code':0})
        row=diagnostic_report(self.j)['commandCoverage'][0]
        self.assertEqual((row['calls'],row['classified'],row['unknown']),(2,1,1))
        self.assertEqual(row['classifiedRate'],.5)
        self.assertIn('Распознаны команды',markdown_pack(report(self.j),'ru'))
        for table in ('observation','call_metadata','capability_evidence','capability_source'):
            for record in self.j.db.execute('SELECT * FROM '+table):
                self.assertNotIn('PRIVATE_',str(tuple(record)));self.assertNotIn(str(self.root),str(tuple(record)))


if __name__=='__main__':unittest.main()
