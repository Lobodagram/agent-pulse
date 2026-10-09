#!/usr/bin/env python3
"""Repeatable source/archive checks and a reviewed handoff, no native clients or models."""
import sys
if sys.version_info<(3,11):
    print('Agent Pulse workflow checks require Python 3.11 or newer.',file=sys.stderr);raise SystemExit(2)
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.parse
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.public_export import export
from journal import atomic_json
from pulse_version import __version__
from check_receipts import Reporter
from journal import PROVIDERS

def archives(directory,version):
    names=['agent-pulse-macos-arm64.zip','agent-pulse-macos-x64.zip','agent-pulse-windows-x64.zip']
    directory=Path(directory);sums={r.split()[1]:r.split()[0] for r in (directory/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()}
    results=[]
    for name in names:
        path=directory/name
        if path.is_symlink():raise ValueError('symlink_archive')
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if sums.get(name)!=digest:raise ValueError('archive_hash_mismatch')
        with zipfile.ZipFile(path) as z:
            entries=z.namelist()
            if any(n.startswith('/') or '..' in Path(n).parts for n in entries):raise ValueError('unsafe_archive_path')
            if not any('pulse-runtime/' in n for n in entries):raise ValueError('missing_runtime')
            for required in ['LICENSE','NOTICE']:
                if not any(n==required or n.endswith('/'+required) for n in entries):raise ValueError('missing_notice')
            checked=False
            if 'macos-' in name:
                import plistlib
                info=next((n for n in entries if n.endswith('.app/Contents/Info.plist')),None)
                if not info or plistlib.loads(z.read(info))['CFBundleShortVersionString']!=version:raise ValueError('archive_version_mismatch')
                checked=True
        results.append({'name':name,'sha256':digest,'versionChecked':checked,'binaryExecuted':False})
    return results

def source_check():
    checks={};version=__version__
    with tempfile.TemporaryDirectory() as tmp:
        tree=Path(tmp)/'public';manifest=export(tree);files=[tree/f for f in manifest['files']]
        for f in files:
            if f.suffix=='.py':ast.parse(f.read_text(encoding='utf-8'),filename=f.name)
        count=0
        for f in files:
            if f.suffix!='.md':continue
            for target in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)',f.read_text(encoding='utf-8')):
                if target.startswith(('https:','http:','#','mailto:')):continue
                target=urllib.parse.unquote(target.split('#')[0])
                if not (f.parent/target).exists():raise ValueError('missing_document_link')
                count+=1
        digest=hashlib.sha256()
        for f in sorted(files):digest.update(str(f.relative_to(tree)).encode()+b'\0'+hashlib.sha256(f.read_bytes()).digest())
        checks['sourceTreeSha256']=digest.hexdigest()
        checks.update(publicFiles=len(files),pythonSyntax='passed',documentLinks=count,privacyExport='passed')
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests'],cwd=ROOT,capture_output=True,text=True,timeout=60)
    checks['unitTests']='passed' if test.returncode==0 else 'failed'
    match=re.search(r'Ran (\d+) tests?',test.stderr);checks['unitTestCount']=int(match[1]) if match else None
    # Failure tracebacks may contain local paths/payloads; never include them in this pack.
    return version,checks

def handoff(result):
    if not isinstance(result,dict) or result.get('schemaVersion')!=1 or not isinstance(result.get('checks'),dict):raise ValueError('invalid_check_result')
    version=result.get('version');commit=result.get('sourceCommit');dirty=result.get('sourceDirty')
    if not isinstance(version,str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version):raise ValueError('invalid_version')
    if commit is not None and (not isinstance(commit,str) or not re.fullmatch('[a-f0-9]{40}',commit)):raise ValueError('invalid_commit')
    if type(dirty)!=bool:raise ValueError('invalid_dirty_status')
    checks={}
    tree=result['checks'].get('sourceTreeSha256')
    if not isinstance(tree,str) or not re.fullmatch('[a-f0-9]{64}',tree):raise ValueError('invalid_tree_digest')
    checks['sourceTreeSha256']=tree
    for k in ['unitTests','pythonSyntax','privacyExport']:
        if result['checks'].get(k) not in {'passed','failed'}:raise ValueError('invalid_check_status')
        checks[k]=result['checks'][k]
    for k in ['unitTestCount','publicFiles','documentLinks']:
        v=result['checks'].get(k)
        if type(v)!=int or not 0<=v<=100000:raise ValueError('invalid_check_count')
        checks[k]=v
    return {'schemaVersion':1,'version':version,'sourceCommit':commit,'sourceDirty':dirty,
            'checks':checks,'nextAction':'Review open platform/native-coverage gates before publishing or deploying.',
            'limits':['Checks are not employee acceptance, full client coverage or measured subscription savings.'],
            'peerStarted':False,'modelsCalled':0}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['check','handoff']);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--input',type=Path);parser.add_argument('--archives',type=Path)
    parser.add_argument('--pulse-state',type=Path,help='Explicit opt-in receipt destination; no native observer changes')
    parser.add_argument('--pulse-provider',choices=sorted(PROVIDERS),help='Reporter-declared client; not native invocation evidence')
    args=parser.parse_args()
    if args.pulse_state and (not args.pulse_provider or args.mode!='check'):parser.error('receipt collection requires check and --pulse-provider')
    reporter=Reporter(args.pulse_state,args.pulse_provider,'workflow-check',__version__)
    try:
        if args.mode=='handoff':
            if not args.input or args.input.is_symlink() or args.input.stat().st_size>32768:raise ValueError('invalid_check_file')
            result=handoff(json.loads(args.input.read_text(encoding='utf-8')))
        else:
            version,checks=source_check();head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,timeout=5)
            commit=head.stdout.strip() if head.returncode==0 and re.fullmatch('[a-f0-9]{40}',head.stdout.strip()) else None
            dirty=subprocess.run(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,capture_output=True,text=True,timeout=5)
            if dirty.returncode:raise ValueError('source_status_unavailable')
            result={'schemaVersion':1,'version':version,'sourceCommit':commit,'sourceDirty':bool(dirty.stdout),'checks':checks,'modelsCalled':0,'peerStarted':False}
            if args.archives:result['archives']=archives(args.archives,version)
        atomic_json(args.output,result)
        gates={g:result['checks'].get(k,'unknown') for g,k in [('unit-tests','unitTests'),('syntax','pythonSyntax'),('privacy-export','privacyExport')]} if args.mode=='check' else {}
        if args.mode=='check':
            gates['links']='passed'
            if args.archives:gates['archives']='passed'
        receipt_saved=reporter.finish('failed' if 'failed' in gates.values() else 'success',gates,result.get('checks',{}).get('sourceTreeSha256',''))
        print(json.dumps({'saved':True,'version':result.get('version'),'checks':result.get('checks'),'modelsCalled':0,'receiptSaved':receipt_saved}))
        return 1 if result.get('checks',{}).get('unitTests')=='failed' else 0
    except KeyboardInterrupt:
        reporter.finish('interrupted');raise
    except Exception as e:
        reporter.finish('failed',{'execution':'failed'})
        print(json.dumps({'error':type(e).__name__,'saved':False}));return 1

if __name__=='__main__':raise SystemExit(main())
