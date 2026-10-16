import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts.workflow_check import save_test_log, main


class WorkflowTestLogTests(unittest.TestCase):
    def test_failure_trace_is_local_and_not_in_summary(self):
        failure=subprocess.CompletedProcess([],1,stdout='PRIVATE_TEST_VALUE',stderr='Traceback: PRIVATE_TEST_PATH')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'log/tests.log'
            result=save_test_log(failure,path)
            self.assertIn('PRIVATE_TEST_PATH',path.read_text(encoding="utf-8"))
            self.assertNotIn('PRIVATE',json.dumps(result))
            self.assertNotIn(str(path),json.dumps(result))
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode&0o777,0o600)
                self.assertEqual(path.parent.stat().st_mode&0o777,0o700)

    def test_log_is_bounded_without_cutting_utf8_tail(self):
        failure=subprocess.CompletedProcess([],1,stdout='x'*50000,stderr='я'*20000+'FAIL END')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'tests.log';result=save_test_log(failure,path)
            self.assertTrue(result['localTestLogTruncated'])
            self.assertLess(path.stat().st_size,32768)
            self.assertTrue(path.read_text(encoding="utf-8").endswith('FAIL END'))

    def test_opt_in_and_symlink_destination(self):
        failure=subprocess.CompletedProcess([],1,stdout='',stderr='PRIVATE')
        self.assertEqual(save_test_log(failure,None),{'localTestLogSaved':False})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'original';target.write_text('keep')
            link=root/'link';link.symlink_to(target)
            with self.assertRaises(ValueError):save_test_log(failure,link)
            self.assertEqual(target.read_text(),'keep')

    def test_log_cannot_be_overwritten_by_summary_at_same_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=str(Path(tmp)/'check.json')
            with patch('sys.argv',['workflow_check','check','--output',output,'--test-log',output]), \
                 patch('scripts.workflow_check.source_check') as run:
                with self.assertRaises(SystemExit):main()
                run.assert_not_called()


if __name__=='__main__':unittest.main()
