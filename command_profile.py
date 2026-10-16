"""Bounded shell classification, never execution or arbitrary-code interpretation."""
from pathlib import PurePosixPath
import json
import re
import shlex

WORDS = {'-m','unittest','pytest','discover','test','run','build','status','diff',
         'log','show','rev-parse','--version','-s','-v','-q','-n','--files','-c',
         '-C','--check','--stat','--short','--porcelain','install','--prefix'}
KNOWN = {'python','python3','pytest','npm','pnpm','bun','cargo','swiftc','git','rg',
         'grep','cat','sed','head','tail','which','sw_vers','node','build.sh',
         'shasum','sha256sum','unzip','zip','plutil','curl','blender'}
KNOWN |= {'cd','pwd','ls','find','wc','sort','uniq','jq','mkdir','cp','mv','rm','touch',
          'chmod','sleep','ps','lsof','du','df','date','make','cmake','xcodebuild',
          'tsc','yarn','npx','bash','sh','zsh','ssh','scp','rsync'}
KNOWN |= {'echo','printf'}
SHELL_TOOLS = {'bash','shell','exec_command','execute','run_shell_command','terminal'}
RECOGNITION_REASONS = {'classified', 'missing-command', 'command-size-limit', 'unsupported-heredoc',
                       'shell-substitution', 'line-count-limit', 'unsupported-redirection',
                       'incomplete-quoting', 'chain-parse-or-limit', 'unrecognized-invocation', 'partial-chain'}

def shell_tool(tool):
    return tool.lower().removeprefix('functions.').removeprefix('functions__') in SHELL_TOOLS

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
    if name in {'skill','use_skill'}:return 'skill.invoke'
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

def classification_command(command, rejections=None):
    """Projection only: discard a terminal here-doc body and literal redirects.

    The strict parts() parser used for skill-read evidence stays unchanged. A
    script's outer invocation never establishes what its opaque code does.
    """
    def reject(reason):
        if rejections is not None:rejections.append(reason)
        return None
    if not isinstance(command,str) or not command.strip():return reject('missing-command')
    if len(command)>32768:return reject('command-size-limit')
    # Support one terminal here-doc, with a simple delimiter outside quotes.
    lines=command.splitlines(keepends=True);quote=None;escape=False
    for n,line in enumerate(lines):
        here=None
        for i,c in enumerate(line):
            if escape:escape=False;continue
            if c=='\\' and quote!="'":escape=True;continue
            if quote:
                if c==quote:quote=None
                continue
            if c in ('"',"'"):quote=c;continue
            if line[i:i+2]=='<<':here=i;break
        if here is None:continue
        match=re.fullmatch(r"<<(-?)[ \t]*(?:'([A-Za-z_][A-Za-z0-9_]{0,63})'|\"([A-Za-z_][A-Za-z0-9_]{0,63})\"|([A-Za-z_][A-Za-z0-9_]{0,63}))[ \t]*(?:\r?\n)?",line[here:])
        if not match:return reject('unsupported-heredoc')
        marker=next(v for v in match.groups()[1:] if v is not None)
        close=next((k for k in range(n+1,len(lines)) if
                    (lines[k].rstrip('\r\n').lstrip('\t') if match[1] else lines[k].rstrip('\r\n'))==marker),None)
        if close is None or any(v.strip() for v in lines[close+1:]):return reject('unsupported-heredoc')
        command=''.join(lines[:n])+line[:here]
        break
    if any(v in command for v in ('$(',chr(96))):return reject('shell-substitution')
    # Strip simple output/input redirects, never execute or resolve targets.
    out=[];quote=None;escape=False;i=0;newlines=0
    while i<len(command):
        c=command[i]
        if escape:out.append(c);escape=False;i+=1;continue
        if c=='\\' and quote!="'":out.append(c);escape=True;i+=1;continue
        if quote:
            out.append(c)
            if c==quote:quote=None
            i+=1;continue
        if c in ('"',"'"):out.append(c);quote=c;i+=1;continue
        if c=='#' and (i==0 or command[i-1].isspace()):
            i=command.find('\n',i)
            if i<0:break
            continue
        if c in '\r\n':
            newlines+=1
            if newlines>64:return reject('line-count-limit')
            if ''.join(out).rstrip() and ''.join(out).rstrip()[-1] not in ';|&':out.append(';')
            i+=1;continue
        if c not in '<>':out.append(c);i+=1;continue
        # Remove an optional adjacent file descriptor, not digits in a word.
        prefix=''.join(out)
        fd=re.search(r'(?:^|\s)([0-9]{1,2})$',prefix)
        if fd:out=out[:-len(fd[1])]
        op=c;i+=1
        if i<len(command) and command[i]==c:op+=c;i+=1
        if op=='<<' or i<len(command) and command[i] in '<>':return reject('unsupported-redirection')
        while i<len(command) and command[i] in ' \t':i+=1
        if i==len(command) or command[i] in ';|\n\r(':return reject('unsupported-redirection')
        if command[i]=='&':
            match=re.match(r'&(?:[0-9]{1,2}|-)(?=\s|[;&|<>]|$)',command[i:])
            if not match:return reject('unsupported-redirection')
            i+=len(match[0])
        else:
            start=i;target_quote=None;target_escape=False
            while i<len(command):
                t=command[i]
                if target_escape:target_escape=False;i+=1;continue
                if t=='\\' and target_quote!="'":target_escape=True;i+=1;continue
                if target_quote:
                    if t==target_quote:target_quote=None
                    i+=1;continue
                if t in ('"',"'"):target_quote=t;i+=1;continue
                if t.isspace() or t in ';&|<>':break
                i+=1
            if i==start or target_quote or target_escape:return reject('unsupported-redirection')
        out.append(' ')
    if quote or escape:return reject('incomplete-quoting')
    return ''.join(out).strip().rstrip(';').strip()

def operation(segment):
    try:tokens=shlex.split(segment)
    except ValueError:return ('shell','shell <unparsed>','unknown')
    assignment_only=re.fullmatch(r'''\s*(?:[A-Za-z_][A-Za-z0-9_]*=(?:[^ \t'"\\]|\\.|'[^']*'|"(?:[^"\\]|\\.)*")*(?:[ \t]+|$))+\s*''',segment)
    if assignment_only and tokens and all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*',t) for t in tokens):
        return ('environment','shell <assignment>','shell-assignment')
    while tokens and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*',tokens[0]):tokens.pop(0)
    if tokens and tokens[0]=='env':
        tokens.pop(0)
        if tokens[:1]==['-i']:tokens.pop(0)
        while tokens and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*',tokens[0]):tokens.pop(0)
    if len(tokens)>2 and tokens[0]=='timeout' and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?[smhd]?',tokens[1]):tokens=tokens[2:]
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
    elif exe in {'npm','pnpm','bun','yarn'}:
        a=args
        if a[:1] in [['--prefix'],['--cwd'],['-C']] and len(a)>2:a=a[2:]
        if a[:1]==['run']:a=a[1:]
        if a[:1] in [['test'],['build']]:kind=a[0];family=exe+'-'+kind
        elif a[:1] in [['lint'],['typecheck'],['check']]:kind='inspect';family=exe+'-'+a[0]
        elif a[:1] in [['start'],['dev']]:kind='run';family=exe+'-'+a[0]
        elif a[:1] in [['install'],['ci'],['add'],['remove']]:kind='edit';family='package-change'
    elif exe=='git' and verb in {'status','diff','log','show','rev-parse'}:
        kind='inspect';family='git-'+verb
    elif exe=='git' and verb in {'clone','fetch','pull'}:kind='remote';family='git-'+verb
    elif exe=='git' and verb in {'add','commit','checkout','switch','restore','reset','merge','rebase'}:kind='edit';family='git-'+verb
    elif exe=='git' and verb=='push':kind='remote';family='git-push'
    elif exe=='git' and verb in {'branch','tag','ls-files','ls-remote'}:kind='inspect';family='git-'+verb
    elif exe in {'shasum','sha256sum'}:kind='inspect';family='checksum'
    elif exe=='unzip':
        kind='inspect' if any(a in {'-l','-t','-tq','-Z','-Z1'} for a in args) else 'edit'
        family='archive-check' if kind=='inspect' else 'archive-extract'
    elif exe=='zip':kind='build';family='archive'
    elif exe=='plutil':kind='inspect' if '-lint' in args or '-p' in args else 'edit';family='plist'
    elif exe=='curl':kind='remote';family='http'
    elif exe=='blender' and any(a in {'-b','--background'} for a in args):kind='build';family='blender-batch'
    elif exe in {'swiftc','build.sh'} or exe=='cargo' and args[:1]==['build']:kind='build'
    elif exe=='cargo' and args[:1] in [['test'],['check']]:kind='test' if args[0]=='test' else 'inspect';family='cargo-'+args[0]
    elif exe=='make':kind='build';family='make-target'
    elif exe in {'cmake','xcodebuild'}:kind='build'
    elif exe=='tsc':kind='inspect' if '--noEmit' in args else 'build';family='typescript'
    elif exe=='npx' and args and args[0] in {'tsc','eslint','vitest','jest'}:
        kind='test' if args[0] in {'vitest','jest'} else 'inspect';family='node-'+args[0]
    elif exe in {'python','python3','node','bash','sh','zsh'}:
        if '--version' in args:kind='environment'
        elif exe in {'python','python3'} and args[:1]==['-m'] and len(args)>1:kind='run';family='python-module'
        elif args[:1] in [['-c'],['-e'],['-lc']]:kind='run';family='python-inline' if exe in {'python','python3'} else 'node-inline' if exe=='node' else 'shell-inline'
        elif args[:1]==['-']:kind='run';family='python-stdin' if exe in {'python','python3'} else 'node-stdin' if exe=='node' else 'shell-stdin'
        elif args and not args[0].startswith('-'):kind='run';family='python-script' if exe in {'python','python3'} else 'node-script' if exe=='node' else 'shell-script'
    elif exe in {'ls','find'}:kind='search'
    elif exe in {'wc','sort','uniq','jq','du','df'}:kind='inspect'
    elif exe in {'cd','pwd','date','sleep'}:kind='environment'
    elif exe in {'ps','lsof'}:kind='inspect';family='process-'+exe
    elif exe in {'mkdir','cp','mv','rm','touch','chmod'}:kind='edit';family='files-'+exe
    elif exe in {'ssh','scp','rsync'}:kind='remote';family=exe+'-transport'
    elif exe in {'echo','printf'}:kind='run';family='shell-output'
    elif exe in {'rg','grep'}:kind='search'
    elif exe in {'cat','sed','head','tail'}:kind='read'
    elif '--version' in args or exe in {'which','sw_vers'}:kind='environment'
    if kind=='shell':family='unknown'
    shape=' '.join([exe]+[v if v in WORDS else '<arg>' for v in args[:19]])
    return kind,shape,family

def profile(command):
    rejections=[]
    normalized=classification_command(command,rejections)
    parsed=parts(normalized) if normalized is not None else None
    if parsed is None:return {'category':'shell','template':'shell <unparsed>','operations':[],'operators':[],
                             'recognitionReason':rejections[0] if rejections else 'chain-parse-or-limit'}
    segments,operators=parsed;ops=[operation(s) for s in segments]
    tokens=[]
    for i,o in enumerate(ops):
        tokens.append(o[1])
        if i<len(operators):tokens.append(operators[i])
    unknown=sum(o[2]=='unknown' for o in ops)
    return {'category':ops[0][0] if len(ops)==1 else 'shell','template':' '.join(tokens),
            'operations':[{'category':o[0],'family':o[2]} for o in ops],'operators':operators,
            'recognitionReason':'unrecognized-invocation' if unknown==len(ops) else 'partial-chain' if unknown else 'classified'}

def command_shape(command):
    p=profile(command);return p['category'],p['template']


COMPONENT_CATEGORIES = {'shell','environment','run','read','search','inspect','test','build','edit','remote'}
COMPONENT_FAMILIES = KNOWN | {'unknown','shell-assignment','shell-output',
    'mesh-topology','slicer-project','mesh-compare','release-preflight','ci-summary','workflow-check','handoff','context-pack',
    'python-test','json','package-change','checksum','archive-check','archive-extract','archive','plist','http','blender-batch',
    'make-target','typescript','python-module','python-inline','node-inline','shell-inline',
    'python-stdin','node-stdin','shell-stdin','python-script','node-script','shell-script'}
COMPONENT_FAMILIES |= {'git-'+v for v in ['status','diff','log','show','rev-parse','clone','fetch','pull','add','commit',
    'checkout','switch','restore','reset','merge','rebase','push','branch','tag','ls-files','ls-remote']}
COMPONENT_FAMILIES |= {e+'-'+v for e in ['npm','pnpm','bun','yarn'] for v in ['test','build','lint','typecheck','check','start','dev']}
COMPONENT_FAMILIES |= {'cargo-test','cargo-check','node-tsc','node-eslint','node-vitest','node-jest'}
COMPONENT_FAMILIES |= {'process-'+v for v in ['ps','lsof']} | {'files-'+v for v in ['mkdir','cp','mv','rm','touch','chmod']}
COMPONENT_FAMILIES |= {v+'-transport' for v in ['ssh','scp','rsync']}


def component_projection(parsed):
    """Fixed operation labels only, not command text or per-component outcomes."""
    return {'operations': parsed['operations'], 'operators': parsed['operators']}


def component_evidence(serialized):
    """Reject malformed/corrupt evidence rather than publish arbitrary fields."""
    if not isinstance(serialized,str) or len(serialized)>8192:return None
    try:data=json.loads(serialized)
    except (ValueError,RecursionError):return None
    if not isinstance(data,dict) or set(data)!={'operations','operators'}:return None
    ops,operators=data['operations'],data['operators']
    if (not isinstance(ops,list) or len(ops)>32 or not isinstance(operators,list) or
        len(operators)!=max(0,len(ops)-1) or any(op not in [';','&&','||','|'] for op in operators)):return None
    if any(not isinstance(o,dict) or set(o)!={'category','family'} or
           not isinstance(o['category'],str) or not isinstance(o['family'],str) or
           o['category'] not in COMPONENT_CATEGORIES or o['family'] not in COMPONENT_FAMILIES for o in ops):return None
    known=sum(o['family']!='unknown' for o in ops)
    state='unparsed' if not ops else 'classified' if known==len(ops) else 'partial' if known else 'unrecognized'
    return {**data,'state':state,'recognized':known,'unknown':len(ops)-known,'total':len(ops),
            'executionVerified':False,'outcomeAttribution':None}
