from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class CliRuntimeTests(unittest.TestCase):
    def old_python(self,*arguments):
        code="import sys,runpy;sys.version_info=(3,9,0);sys.argv=['collector.py']+sys.argv[1:];runpy.run_path('collector.py',run_name='__main__')"
        return subprocess.run([sys.executable,'-c',code,*arguments],cwd=ROOT,capture_output=True,text=True)
    def test_old_python_gets_safe_message_before_imports(self):
        r=self.old_python('catalog')
        self.assertEqual(r.returncode,1);self.assertIn('Python 3.11',r.stderr);self.assertNotIn('Traceback',r.stderr);self.assertEqual(r.stdout,'')
    def test_old_python_hook_stays_silent(self):
        r=self.old_python('hook','--provider','codex')
        self.assertEqual((r.returncode,r.stdout,r.stderr),(0,'',''))
    def test_debug_contains_class_but_never_exception_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret_path=str(Path(tmp)/'SensitiveCanary-do-not-print.json')
            r=subprocess.run([sys.executable,'collector.py','--state',tmp,'--debug','ingest','--provider','codex','--file',secret_path],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(r.returncode,1);self.assertIn('FileNotFoundError',r.stderr)
            self.assertNotIn('SensitiveCanary',r.stdout+r.stderr);self.assertNotIn(tmp,r.stdout+r.stderr)
            self.assertEqual(r.stdout.strip(),'{"error":"collector_unavailable"}')
