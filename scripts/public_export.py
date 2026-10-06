#!/usr/bin/env python3
"""Export an allowlisted public tree; no private Git history or runtime data."""
from pathlib import Path
import argparse
import json
import re
import shutil
ROOT=Path(__file__).resolve().parents[1]
FILES=['collector.py','providers.py','platform_support.py','build.sh','requirements-build.txt','LICENSE','README.md','README.ru.md','PRIVACY.md','SECURITY.md','CONTRIBUTING.md','CHANGELOG.md','NOTICE','COMMERCIAL_LICENSE.md','.gitignore']
DIRS=['Sources','windows','tests','scripts','docs','examples','.github']
def export(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('destination_exists')
    destination.mkdir(parents=True)
    selected=[ROOT/name for name in FILES]
    for name in DIRS:
        selected += [p for p in (ROOT/name).rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix not in ('.pyc',) and not p.name.endswith('.png.json')]
    for source in selected:
        if source.is_symlink():raise ValueError('symlink_source')
        data=source.read_bytes();rel=source.relative_to(ROOT)
        if source.suffix!='.png':
            text=data.decode('utf-8')
            patterns=[r'/Users/[A-Za-z0-9_.@-]+',r'bioclaude\.biocard',r'bcm_[A-Za-z0-9_-]{25,}',r'github_pat_[A-Za-z0-9_]{25,}',r'ghp_[A-Za-z0-9]{25,}',r'sk-[A-Za-z0-9]{25,}']
            # Scanner patterns themselves are not credentials and intentionally remain public.
            if any(re.search(x,text) for x in patterns):raise ValueError('private_content_in_'+str(rel))
        target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    public_agent='''# Agent Pulse contributor instructions\n\nRead README.md, PRIVACY.md and docs/PROVIDERS.md. Keep native clients read-only. Never call models, scrape credentials, start sessions or upload telemetry. Preserve unknown values and source/coverage labels. Run `python -m unittest discover -s tests -v`. UI screenshots must use `examples/demo.json`; never publish account or conversation data. No company rules, private home paths or runtime state belongs in this repository. Commercial contributor rights are described in CONTRIBUTING.md.\n'''
    (destination/'AGENTS.md').write_text(public_agent)
    manifest={'files':sorted(str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()),'privateHistoryIncluded':False,'demoOnly':True}
    return manifest
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('destination');args=a.parse_args();print(json.dumps(export(args.destination),indent=2))
