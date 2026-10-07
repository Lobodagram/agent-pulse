#!/usr/bin/env python3
"""Install the reviewed source skill pack to an explicit directory, never overwrite."""
import argparse
from pathlib import Path
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[1]
NAMES=('agent-pulse-setup','agent-pulse-analysis')
def install(destination):
    destination=Path(destination).expanduser().absolute()
    if any(p.is_symlink() for p in (destination,*destination.parents)):raise ValueError('symlink_destination')
    if any((destination/n).exists() or (destination/n).is_symlink() for n in NAMES):raise ValueError('existing_skill_preserved')
    destination.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'agent-skills'/n for n in NAMES]
    for source in sources:
        if not (source/'SKILL.md').is_file() or any(p.is_symlink() for p in source.rglob('*')):raise ValueError('invalid_source')
    installed=[]
    try:
        with tempfile.TemporaryDirectory(prefix='.agent-pulse-',dir=destination) as temporary:
            for source in sources:shutil.copytree(source,Path(temporary)/source.name)
            for name in NAMES:
                # Exclusive mkdir prevents concurrent installation from overwriting another skill.
                target=destination/name;target.mkdir();installed.append(target)
                for item in (Path(temporary)/name).iterdir():shutil.move(str(item),str(target/item.name))
    except Exception:
        for target in installed:shutil.rmtree(target)
        raise
    return {'installed':list(NAMES),'existingSkillsPreserved':True}
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--destination',type=Path,required=True);args=a.parse_args()
    import json
    try:print(json.dumps(install(args.destination)))
    except Exception as error:raise SystemExit('Agent Pulse skill installation failed: '+type(error).__name__)
