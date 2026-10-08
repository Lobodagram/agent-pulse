"""Platform paths and runtime discovery; never locates credentials or conversations."""
import os
from pathlib import Path
import shutil
import sys
import subprocess

WINDOWS_RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
WINDOWS_RUN_NAME = 'AgentPulse'

def windows_startup_command(executable=None, script=None, frozen=None):
    """Exact executable/script only; never preserve fixture or arbitrary CLI flags."""
    frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    executable = Path(executable or sys.executable).resolve()
    if not frozen:
        windowless = executable.with_name('pythonw.exe')
        if windowless.is_file(): executable = windowless
        script = Path(script or Path(__file__).parent/'windows/agent_pulse.py').resolve()
    command = subprocess.list2cmdline([str(executable)] if frozen else [str(executable), str(script)])
    if len(command) > 260 or any(c in command for c in '\r\n\x00'):
        raise ValueError('startup_command_invalid')
    return command

def windows_launch_at_login(enabled=None):
    """Read/write this app's current-user Run value; no elevation or other entries."""
    if sys.platform != 'win32': raise NotImplementedError('windows_only')
    import winreg
    if enabled is not None and type(enabled) is not bool: raise ValueError('boolean_required')
    if enabled is True:
        command = windows_startup_command()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, WINDOWS_RUN_NAME, 0, winreg.REG_SZ, command)
    elif enabled is False:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                try: winreg.DeleteValue(key, WINDOWS_RUN_NAME)
                except FileNotFoundError: pass
        except FileNotFoundError: pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_QUERY_VALUE) as key:
            value, kind = winreg.QueryValueEx(key, WINDOWS_RUN_NAME)
    except FileNotFoundError: return False
    # An older install path still counts as registered, so the checkbox can
    # remove it. Enabling writes the current exact path.
    return kind == winreg.REG_SZ and isinstance(value, str) and bool(value)

def state_directory():
    if sys.platform=='win32':return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'AgentPulse'
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/AgentPulse'
    return Path(os.environ.get('XDG_STATE_HOME',Path.home()/'.local/state'))/'agent-pulse'

def find_node():
    value=shutil.which('node')
    if value:return Path(value)
    return Path('node')

def zcode_paths(config):
    root=Path(config.get('zcodeResources') or ('/Applications/ZCode.app/Contents/Resources' if sys.platform=='darwin' else Path(os.environ.get('LOCALAPPDATA',''))/'Programs/ZCode/resources'))
    entry=Path(config.get('zcodeCli') or root/'glm/zcode.cjs')
    builtin=Path(config.get('zcodeBuiltin') or root/'config/provider/zcode-builtin.json')
    return entry,builtin
