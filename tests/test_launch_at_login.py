import contextlib
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import platform_support as platform


class WindowsStartupTests(unittest.TestCase):
    def registry(self):
        values={'OtherApp':('untouched',1)}
        def query(key,name):
            if name not in values: raise FileNotFoundError
            return values[name]
        def delete(key,name):
            if name not in values: raise FileNotFoundError
            del values[name]
        registry=types.SimpleNamespace(HKEY_CURRENT_USER=1,KEY_SET_VALUE=2,KEY_QUERY_VALUE=4,REG_SZ=1,
            CreateKeyEx=lambda *a:contextlib.nullcontext('key'),OpenKey=lambda *a:contextlib.nullcontext('key'),
            SetValueEx=lambda key,name,reserved,kind,value:values.__setitem__(name,(value,kind)),
            QueryValueEx=query,DeleteValue=delete)
        return registry,values

    def test_current_user_registration_inverse_and_old_paths(self):
        registry,values=self.registry()
        with patch.object(platform.sys,'platform','win32'),patch.dict(sys.modules,{'winreg':registry}),patch.object(platform,'windows_startup_command',return_value='"current app.exe"'):
            self.assertFalse(platform.windows_launch_at_login())
            self.assertTrue(platform.windows_launch_at_login(True))
            self.assertEqual(values['AgentPulse'],('"current app.exe"',1))
            values['AgentPulse']=('"old app.exe"',1)
            self.assertTrue(platform.windows_launch_at_login())
            self.assertFalse(platform.windows_launch_at_login(False))
            self.assertFalse(platform.windows_launch_at_login(False))
            self.assertEqual(values,{'OtherApp':('untouched',1)})

    def test_access_denied_is_not_reported_as_success(self):
        registry,values=self.registry()
        registry.CreateKeyEx=lambda *a:(_ for _ in ()).throw(PermissionError())
        with patch.object(platform.sys,'platform','win32'),patch.dict(sys.modules,{'winreg':registry}),patch.object(platform,'windows_startup_command',return_value='app.exe'):
            with self.assertRaises(PermissionError):platform.windows_launch_at_login(True)
            self.assertNotIn('AgentPulse',values)

    def test_quoted_paths_no_fixture_arguments_and_length_limit(self):
        with tempfile.TemporaryDirectory(prefix='startup path ') as tmp:
            exe=Path(tmp).resolve()/'Agent Pulse.exe';script=Path(tmp).resolve()/'agent pulse.py'
            with patch.object(sys,'argv',['app','--fixture','PRIVATE_CANARY','--smoke']):
                self.assertEqual(platform.windows_startup_command(exe,frozen=True),subprocess.list2cmdline([str(exe)]))
                command=platform.windows_startup_command(exe,script,frozen=False)
                self.assertEqual(command,subprocess.list2cmdline([str(exe),str(script)]))
                self.assertNotIn('PRIVATE_CANARY',command)
            with self.assertRaises(ValueError):platform.windows_startup_command(Path(tmp)/('a'*270),frozen=True)


@unittest.skipUnless(sys.platform=='darwin','macOS Swift/ServiceManagement contract')
class MacStartupTests(unittest.TestCase):
    def test_native_controller_states_failures_and_preview_isolation(self):
        harness='''
import Foundation
@MainActor final class Fake: LoginItemService {
    var state: LoginItemStatus = .disabled
    var reads = 0; var writes = 0; var deny = false; var approval = false
    var status: LoginItemStatus { reads += 1; return state }
    func register() throws { writes += 1; if deny { throw NSError(domain: "test", code: 1) }; state = approval ? .requiresApproval : .enabled }
    func unregister() throws { writes += 1; if deny { throw NSError(domain: "test", code: 2) }; state = .disabled }
}
@main struct Checks {
    @MainActor static func main() {
        let fake = Fake()
        let preview = LaunchAtLoginController(service: fake, preview: true, allowed: true)
        preview.setEnabled(true); preview.refresh(); assert(fake.reads == 0 && fake.writes == 0)
        let uninstalled = LaunchAtLoginController(service: fake, preview: false, allowed: false)
        uninstalled.setEnabled(true); assert(fake.reads == 0 && fake.writes == 0)
        let live = LaunchAtLoginController(service: fake, preview: false, allowed: true)
        assert(!live.checked && fake.writes == 0)
        live.setEnabled(true); assert(live.checked && live.status == .enabled && !live.failed)
        live.setEnabled(true); assert(fake.writes == 1)
        live.setEnabled(false); assert(!live.checked && !live.failed)
        fake.approval = true; live.setEnabled(true); assert(live.checked && live.status == .requiresApproval && !live.failed)
        live.setEnabled(false); assert(!live.checked)
        fake.deny = true; live.setEnabled(true); assert(!live.checked && live.failed)
        fake.state = .enabled; live.refresh(); live.setEnabled(false); assert(live.checked && live.failed)
        fake.state = .disabled; live.refresh(); assert(!live.checked)
        print("passed: preview/install boundaries, enable/disable/idempotence, approval, denied writes, external changes")
    }
}
'''
        source=Path(__file__).resolve().parents[1]/'Sources/LaunchAtLogin.swift'
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'Checks.swift';file.write_text(harness);exe=Path(tmp)/'checks'
            built=subprocess.run(['xcrun','swiftc','-parse-as-library',str(source),str(file),'-framework','ServiceManagement','-o',str(exe)],capture_output=True,text=True,timeout=60)
            self.assertEqual(built.returncode,0,built.stderr)
            checked=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
            self.assertEqual(checked.returncode,0,checked.stderr)


if __name__=='__main__':unittest.main()
