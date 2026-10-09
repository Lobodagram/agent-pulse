import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import public_export


class BrandExportTests(unittest.TestCase):
    def test_unreviewed_binary_and_wrong_format_cannot_bypass_text_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'brand').mkdir();(root/'docs/screenshots').mkdir(parents=True)
            (root/'docs/screenshots/manifest.json').write_text('{}')
            icon=root/'brand/logo.ico';icon.write_bytes(b'PRIVATE_CANARY')
            manifest=root/'brand/manifest.json';manifest.write_text('{}')
            with patch.object(public_export,'ROOT',root),patch.object(public_export,'FILES',[]),patch.object(public_export,'DIRS',['brand']):
                with self.assertRaisesRegex(ValueError,'unreviewed_brand'):public_export.export(root/'unreviewed')
                manifest.write_text(json.dumps({'brand/logo.ico':hashlib.sha256(icon.read_bytes()).hexdigest()}))
                with self.assertRaisesRegex(ValueError,'invalid_brand_format'):public_export.export(root/'invalid')
                icon.write_bytes(b'\x00\x00\x01\x00TEST_FIXTURE')
                manifest.write_text(json.dumps({'brand/logo.ico':hashlib.sha256(icon.read_bytes()).hexdigest()}))
                receipt=public_export.export(root/'allowed')
                self.assertIn(str(Path('brand/logo.ico')),receipt['files'])

    def test_source_and_frozen_assets_use_the_same_relative_resource(self):
        import importlib.util,sys
        source=Path(__file__).resolve().parents[1]/'windows/pulse_brand.py'
        spec=importlib.util.spec_from_file_location('pulse_brand_test',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.asset('AgentPulse.ico'),source.parents[1]/'brand/AgentPulse.ico')
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS','/fixture-extracted',create=True):
            self.assertEqual(module.asset('AgentPulse.ico'),Path('/fixture-extracted/brand/AgentPulse.ico'))
