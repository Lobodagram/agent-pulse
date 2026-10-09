#!/usr/bin/env python3
"""Export an allowlisted public tree; no private Git history or runtime data."""
from pathlib import Path
import argparse
import json
import re
import shutil
import hashlib
ROOT=Path(__file__).resolve().parents[1]
FILES=['check_receipts.py','collection_health.py','model_evidence.py','command_profile.py','result_metadata.py','capability_report.py','evidence_pack.py','compact_summary.py','journal.py','analytics.py','journal_cli.py','instrumentation.py','mcp_server.py','collector.py','providers.py','platform_support.py','build.sh','requirements-build.txt','LICENSE','LICENSE-MIT.txt','README.md','README.ru.md','PRIVACY.md','SECURITY.md','CONTRIBUTING.md','CHANGELOG.md','NOTICE','COMMERCIAL_LICENSE.md','.gitignore']
FILES += ['agent_control.py','provider_secrets.py','glm_quota.py','sanitizers.py','pulse_version.py','hook_bridge.py','pyproject.toml','session_view.py','capability_detection.py','finding_review.py','review_pack.py','efficiency.py']
DIRS=['agent-skills','script','Sources','windows','tests','scripts','docs','examples','.github','third_party','brand']
def export(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('destination_exists')
    destination.mkdir(parents=True)
    selected=[ROOT/name for name in FILES]
    for name in DIRS:
        selected += [p for p in (ROOT/name).rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix not in ('.pyc',) and not p.name.endswith('.png.json')]
    reviewed=json.loads((ROOT/'docs/screenshots/manifest.json').read_text())
    brand=json.loads((ROOT/'brand/manifest.json').read_text())
    for source in selected:
        if source.is_symlink():raise ValueError('symlink_source')
        data=source.read_bytes();rel=source.relative_to(ROOT)
        if source.name.lower() in {'secrets.json','config.json','auth.json','credentials.json'} or source.suffix.lower() in {'.db','.sqlite','.sqlite3','.log','.zip','.exe','.dmg'}:raise ValueError('runtime_file_in_'+str(rel))
        if rel.parts[0]=='brand' and source.suffix.lower() in ('.png','.ico','.icns'):
            if brand.get(rel.as_posix())!=hashlib.sha256(data).hexdigest():raise ValueError('unreviewed_brand_'+rel.as_posix())
            signature={'.png':b'\x89PNG\r\n\x1a\n','.ico':b'\x00\x00\x01\x00','.icns':b'icns'}[source.suffix.lower()]
            if not data.startswith(signature):raise ValueError('invalid_brand_format_'+rel.as_posix())
        elif source.suffix=='.png':
            if rel.as_posix() not in reviewed or reviewed[rel.as_posix()]!=hashlib.sha256(data).hexdigest():raise ValueError('unreviewed_image_'+rel.as_posix())
        else:
            text=data.decode('utf-8')
            patterns=[r'/Users/[A-Za-z0-9_.@-]+',r'bioclaude\.biocard',r'bcm_[A-Za-z0-9_-]{25,}',r'github_pat_[A-Za-z0-9_]{25,}',r'ghp_[A-Za-z0-9]{25,}',r'sk-[A-Za-z0-9]{25,}']
            # Scanner patterns themselves are not credentials and intentionally remain public.
            if any(re.search(x,text) for x in patterns):raise ValueError('private_content_in_'+str(rel))
        target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    public_agent='''# Agent Pulse contributor instructions\n\nRead README.md, PRIVACY.md, docs/PROVIDERS.md and docs/AGENT_SETUP.md. The portable skills in agent-skills support setup and evidence review. Local MCP is read-only unless the owner explicitly enables --allow-control; do not fabricate review decisions. Keep native clients read-only. Never call models, scrape credentials, start sessions or upload telemetry. Preserve unknown values and source/coverage labels. Run `python -m unittest discover -s tests -v`. UI screenshots must use `examples/demo.json`; never publish account or conversation data. No company rules, private home paths or runtime state belongs in this repository. AGPL-3.0-only contributor rights are described in CONTRIBUTING.md.\n'''
    (destination/'AGENTS.md').write_text(public_agent)
    manifest={'files':sorted(str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()),'privateHistoryIncluded':False,'demoOnly':True}
    return manifest
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('destination');args=a.parse_args();print(json.dumps(export(args.destination),indent=2))
