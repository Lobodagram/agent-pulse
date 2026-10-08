from pathlib import Path
import tempfile
import time
import unittest
from journal import Journal, category
from analytics import findings, report
from command_profile import profile


class PrecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.j=Journal(self.root/'state');self.n=0;self.now=time.time()-1000
    def tearDown(self):self.j.close();self.temp.cleanup()
    def pair(self,tool='Bash',command='git status',turn='t',session='s'):
        self.n+=1
        raw={'session_id':session,'turn_id':turn,'cwd':str(self.root),'tool_use_id':str(self.n),
             'tool_name':tool,'tool_input':{'command':command},'timestamp':self.now+self.n*3}
        self.j.record('codex',dict(raw,hook_event_name='PreToolUse'))
        self.j.record('codex',dict(raw,hook_event_name='PostToolUse',timestamp=raw['timestamp']+1,tool_response={'exit_code':0}))
    def test_allowlisted_shell_families_and_private_arguments(self):
        examples={'shasum -a 256 PRIVATE':'inspect.checksum','unzip -t PRIVATE':'inspect.archive-check',
                  'plutil -lint PRIVATE':'inspect.plist','curl -I https://private.invalid':'remote.http',
                  'git clone PRIVATE':'remote.git-clone','blender --background --python PRIVATE':'build.blender-batch',
                  'python3 mesh_qa.py inspect-mesh PRIVATE':'inspect.mesh-topology'}
        for command,expected in examples.items():
            p=profile(command);self.assertEqual(p['operations'],[dict(zip(('category','family'),expected.split('.')))])
            self.assertNotIn('PRIVATE',str(p));self.assertNotIn('private.invalid',str(p))
        for command in ['python3 - <<EOF\ncode\nEOF','cat $(secret)','curl `secret`','shasum PRIVATE > target']:
            self.assertEqual(profile(command)['operations'],[])
    def test_todo_not_edit_and_historical_bookkeeping_not_findings(self):
        self.assertEqual(category('TodoWrite',{}),'other')
        for n in range(8):self.pair(tool='TodoWrite',turn=str(n))
        calls=self.j.calls()
        # Existing databases may still have the old edit category.
        for c in calls:c['category']='edit'
        self.assertEqual(findings(self.j,calls),[])
        self.assertEqual(report(self.j)['analysisCoverage']['bookkeepingCalls'],8)
    def test_bookkeeping_is_sequence_barrier(self):
        for n in range(3):
            self.pair('Read',turn=str(n));self.pair('TodoWrite',turn=str(n));self.pair('Bash','python3 -m unittest',turn=str(n))
        self.assertFalse(any(f['kind']=='sequence' for f in report(self.j)['findings']))
    def test_exact_repeat_survives_many_broad_sequences(self):
        for n in range(8):self.pair(turn=str(n))
        calls=self.j.calls()
        for n in range(50):
            for turn in range(3):
                for k,cat in enumerate(['read','shell']):
                    calls.append(dict(calls[0],id=f'{n}-{turn}-{k}',project=str(n),session=str(n),turn=str(turn),
                                      category=cat,operation='unknown',fingerprint=f'{n}-{turn}-{k}',
                                      template=f'{n}-{turn}-{k}',startedAt=10+k*2,endedAt=11+k*2))
        result=findings(self.j,calls);self.assertEqual(result[0]['kind'],'repeat_call');self.assertEqual(len(result),30)
        small=findings(self.j,calls,summary_only=True)
        self.assertEqual([f['id'] for f in result],[f['id'] for f in small])
    def test_tool_name_projection_preserves_historical_unknown_shell(self):
        self.pair('mcp__codex_apps__github__fetch_workflow_run_jobs')
        self.pair('mcp__mesh_qa__verify_3mf')
        self.pair('Bash','python3 - <<EOF\nunknown\nEOF')
        self.assertEqual([c['operation'] for c in self.j.calls()],['inspect.github-ci-status','inspect.slicer-project','unknown'])
        self.j.db.execute("UPDATE call_metadata SET signature='remote'");self.j.db.commit()
        self.assertEqual(self.j.calls()[0]['operation'],'inspect.github-ci-status')

    def test_typed_publication_chain_with_one_category_is_visible(self):
        for n in range(3):
            for tool in ['create_tree','create_commit','update_ref']:
                self.pair('mcp__codex_apps__github__'+tool,command=str(n),turn=str(n))
        rows=[f for f in report(self.j)['findings'] if f['kind']=='sequence']
        self.assertTrue(any(f.get('operations')==['remote.github-tree','remote.github-commit','remote.github-ref'] for f in rows))
        self.assertTrue(all(f['confidence']=='medium' for f in rows))


if __name__=='__main__':unittest.main()
