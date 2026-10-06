"""Platform paths and runtime discovery; never locates credentials or conversations."""
import os
from pathlib import Path
import shutil
import sys

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
