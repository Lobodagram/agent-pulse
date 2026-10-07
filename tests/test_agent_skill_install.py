import importlib.util
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('pulse_skill_install',Path(__file__).resolve().parents[1]/'scripts/install_agent_skills.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SkillInstallTests(unittest.TestCase):
    def test_install_and_preserve_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp).resolve()/'skills';destination.mkdir();(destination/'unrelated').mkdir();(destination/'unrelated/file').write_text('keep')
            result=m.install(destination);self.assertEqual(len(result['installed']),2)
            before=(destination/m.NAMES[0]/'SKILL.md').read_bytes()
            with self.assertRaises(ValueError):m.install(destination)
            self.assertEqual(before,(destination/m.NAMES[0]/'SKILL.md').read_bytes());self.assertEqual((destination/'unrelated/file').read_text(),'keep')
    def test_existing_second_name_prevents_partial_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp).resolve();(destination/m.NAMES[1]).mkdir()
            with self.assertRaises(ValueError):m.install(destination)
            self.assertFalse((destination/m.NAMES[0]).exists())
    def test_symlink_parent_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp).resolve();(destination/'real').mkdir()
            try:(destination/'link').symlink_to(destination/'real',target_is_directory=True)
            except OSError:self.skipTest('symlink privileges unavailable')
            with self.assertRaises(ValueError):m.install(destination/'link'/'skills')
