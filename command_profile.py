"""Bounded shell classification, never execution or arbitrary-code interpretation."""
from pathlib import PurePosixPath
import re
import shlex

WORDS = {'-m','unittest','pytest','discover','test','run','build','status','diff',
         'log','show','rev-parse','--version','-s','-v','-q','-n','--files','-c',
         '-C','--check','--stat','--short','--porcelain','install','--prefix'}
KNOWN = {'python','python3','pytest','npm','pnpm','bun','cargo','swiftc','git','rg',
         'grep','cat','sed','head','tail','which','sw_vers','node','build.sh'}

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
    if exe=='pytest' or exe in {'python','python3'} and args[:2] in [['-m','unittest'],['-m','pytest']]:
        kind='test';family='python-test'
    elif exe in {'npm','pnpm','bun'}:
        a=args
        if a[:1]==['--prefix'] and len(a)>2:a=a[2:]
        if a[:1]==['run']:a=a[1:]
        if a[:1] in [['test'],['build']]:kind=a[0];family=exe+'-'+kind
    elif exe=='git' and verb in {'status','diff','log','show','rev-parse'}:
        kind='inspect';family='git-'+verb
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
