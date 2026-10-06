"""Conservative literal reader syntax; never execute, expand or read commands."""
import re
import shlex
from command_profile import parts

READERS={'cat','sed','head','tail'}
SHELL_TOOLS={'bash','shell','exec_command','execute','run_shell_command','terminal'}

def literal_reads(tool,args):
    if tool.lower() not in SHELL_TOOLS or not isinstance(args,dict):return []
    command=args.get('command',args.get('cmd'))
    if not isinstance(command,str) or any(c in command for c in '$`~*?[]{}#'):return []
    parsed=parts(command)
    if not parsed:return []
    segments,operators=parsed
    # Exit zero from a ;/||/pipeline does not establish that earlier readers ran.
    if any(op!='&&' for op in operators):return []
    paths=[]
    for segment in segments:
        try:words=shlex.split(segment)
        except ValueError:return []
        if not words:return []
        exe=words.pop(0)
        reader=exe.rsplit('/',1)[-1]
        if reader not in READERS or exe not in {reader,'/bin/'+reader,'/usr/bin/'+reader}:return []
        if reader=='sed':
            if len(words)<3 or words[0]!='-n' or not re.fullmatch(r'[1-9][0-9]*(?:,[1-9][0-9]*)?p',words[1]):return []
            bounds=words[1][:-1].split(',')
            if len(bounds)==2 and int(bounds[1])<int(bounds[0]):return []
            words=words[2:]
        elif reader in {'head','tail'}:
            if words[:1]==['-n']:
                if len(words)<3 or not re.fullmatch(r'[1-9][0-9]{0,5}',words[1]):return []
                words=words[2:]
            elif words and re.fullmatch(r'-n[1-9][0-9]{0,5}',words[0]):words=words[1:]
        if words[:1]==['--']:words=words[1:]
        if not words or any(not w or w.startswith('-') or len(w)>4096 for w in words):return []
        paths.extend(words)
        if len(paths)>32:return []
    return list(dict.fromkeys(paths))

def mcp_namespace(tool):
    if not isinstance(tool,str):return None
    if tool.startswith('functions.'):tool=tool[len('functions.'):]
    if not tool.startswith('mcp__'):return None
    components=tool[5:].split('__',1)
    if len(components)!=2 or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,80}',components[0]) or not components[1]:return None
    return components[0]
