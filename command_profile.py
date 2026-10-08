"""Bounded shell classification, never execution or arbitrary-code interpretation."""
from pathlib import PurePosixPath
import re
import shlex

WORDS = {'-m','unittest','pytest','discover','test','run','build','status','diff',
         'log','show','rev-parse','--version','-s','-v','-q','-n','--files','-c',
         '-C','--check','--stat','--short','--porcelain','install','--prefix'}
KNOWN = {'python','python3','pytest','npm','pnpm','bun','cargo','swiftc','git','rg',
         'grep','cat','sed','head','tail','which','sw_vers','node','build.sh',
         'shasum','sha256sum','unzip','zip','plutil','curl','blender'}

# Names identify an operation family, not executable provenance or successful use.
HELPERS = {
    'mesh_qa.py': {'inspect-mesh': ('inspect','mesh-topology'), 'verify-3mf': ('inspect','slicer-project'),
                   'compare-versions': ('inspect','mesh-compare')},
    'release_workflow.py': {'prepare': ('inspect','release-preflight'), 'ci': ('inspect','ci-summary')},
    'workflow_check.py': {'check': ('test','workflow-check'), 'handoff': ('inspect','handoff')},
    'workflow_context.py': {'--root': ('inspect','context-pack')},
}

CONTROL_TOOLS = {'todowrite','todo_write','update_plan','clocksleep','clock__sleep',
                 'request_user_input','request_user_input_async'}

def control_tool(tool):
    return tool.lower().removeprefix('functions.').removeprefix('functions__') in CONTROL_TOOLS

def tool_operation(tool, category):
    """Fixed names only; namespaces never imply connection or substitution."""
    name=tool.lower().removeprefix('functions.')
    if control_tool(name):return 'bookkeeping'
    for namespace in ('mcp__mesh_qa__','mcp__mesh-qa__'):
        if name.startswith(namespace):
            return {'inspect_mesh':'inspect.mesh-topology','verify_3mf':'inspect.slicer-project',
                    'compare_versions':'inspect.mesh-compare'}.get(name[len(namespace):],category)
    for namespace in ('mcp__codex_apps__github__','mcp__codex_apps__github_'):
        if name.startswith(namespace):
            return {'create_blob':'remote.github-blob','create_tree':'remote.github-tree',
                    'create_commit':'remote.github-commit','update_ref':'remote.github-ref',
                    'fetch_workflow_run_jobs':'inspect.github-ci-status',
                    'fetch_workflow_job_logs':'read.github-ci-logs'}.get(name[len(namespace):],category)
    return category

def parts(command):
    if not isinstance(command,str) or len(command)>32768:return None
    if any(x in command for x in ('$(',chr(96),'<<')):return None
    quote=None;escape=False;start=0;segments=[];operators=[];i=0
    while i<len(command):
        c=command[i]
        if escape:escape=False;i+=1;continue
        if c=='\\' and quote!="'":escape=True;i+=1;continue
        if quote:
            if c==quote:quote=None
            i+=1;continue
        if c in ('"',"'"):quote=c;i+=1;continue
        if c in '<>\n\r':return None
        if c in ';&|':
            op=c
            if command[i:i+2] in ('&&','||'):op=command[i:i+2]
            elif c=='&':return None
            segments.append(command[start:i]);operators.append(op)
            i+=len(op);start=i
            if len(segments)>31:return None
        else:i+=1
    if quote or escape:return None
    segments.append(command[start:])
    if any(not s.strip() for s in segments):return None
    return segments,operators

def operation(segment):
    try:tokens=shlex.split(segment)
    except ValueError:return ('shell','shell <unparsed>','unknown')
    while tokens and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*',tokens[0]):tokens.pop(0)
    if not tokens:return ('shell','shell <empty>','unknown')
    exe=PurePosixPath(tokens[0].replace('\\','/')).name
    if re.fullmatch(r'python3(?:\.\d+){0,2}',exe):exe='python3'
    if exe not in KNOWN:return ('shell','shell <command>','unknown')
    args=tokens[1:];verb=''
    if exe=='git':
        i=0
        while i<len(args):
            if args[i] in {'-C','-c','--git-dir','--work-tree'}:i+=2
            elif args[i].startswith(('--git-dir=','--work-tree=')):i+=1
            elif args[i].startswith('-'):i+=1
            else:verb=args[i];break
    kind='shell';family=exe
    script=PurePosixPath(args[0].replace('\\','/')).name if args else ''
    if exe in {'python','python3'} and script in HELPERS and len(args)>1 and args[1] in HELPERS[script]:
        kind,family=HELPERS[script][args[1]]
    elif exe=='pytest' or exe in {'python','python3'} and args[:2] in [['-m','unittest'],['-m','pytest']]:
        kind='test';family='python-test'
    elif exe in {'python','python3'} and args[:2]==['-m','json.tool']:kind='inspect';family='json'
    elif exe in {'npm','pnpm','bun'}:
        a=args
        if a[:1]==['--prefix'] and len(a)>2:a=a[2:]
        if a[:1]==['run']:a=a[1:]
        if a[:1] in [['test'],['build']]:kind=a[0];family=exe+'-'+kind
    elif exe=='git' and verb in {'status','diff','log','show','rev-parse'}:
        kind='inspect';family='git-'+verb
    elif exe=='git' and verb in {'clone','fetch','pull'}:kind='remote';family='git-'+verb
    elif exe in {'shasum','sha256sum'}:kind='inspect';family='checksum'
    elif exe=='unzip':
        kind='inspect' if any(a in {'-l','-t','-tq','-Z','-Z1'} for a in args) else 'edit'
        family='archive-check' if kind=='inspect' else 'archive-extract'
    elif exe=='zip':kind='build';family='archive'
    elif exe=='plutil':kind='inspect' if '-lint' in args or '-p' in args else 'edit';family='plist'
    elif exe=='curl':kind='remote';family='http'
    elif exe=='blender' and any(a in {'-b','--background'} for a in args):kind='build';family='blender-batch'
    elif exe in {'swiftc','build.sh'} or exe=='cargo' and args[:1]==['build']:kind='build'
    elif exe in {'rg','grep'}:kind='search'
    elif exe in {'cat','sed','head','tail'}:kind='read'
    elif '--version' in args or exe in {'which','sw_vers'}:kind='environment'
    if kind=='shell':family='unknown'
    shape=' '.join([exe]+[v if v in WORDS else '<arg>' for v in args[:19]])
    return kind,shape,family

def profile(command):
    parsed=parts(command)
    if parsed is None:return {'category':'shell','template':'shell <unparsed>','operations':[],'operators':[]}
    segments,operators=parsed;ops=[operation(s) for s in segments]
    tokens=[]
    for i,o in enumerate(ops):
        tokens.append(o[1])
        if i<len(operators):tokens.append(operators[i])
    return {'category':ops[0][0] if len(ops)==1 else 'shell','template':' '.join(tokens),
            'operations':[{'category':o[0],'family':o[2]} for o in ops],'operators':operators}

def command_shape(command):
    p=profile(command);return p['category'],p['template']
