"""Project result metadata only. Shell stdout is never evidence of an exit code."""
import json
import math

SHELL = {'bash','shell','exec_command','functions.exec_command','functions.exec','exec','terminal'}

def exit_code(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and -255<=value<=255 else None

def classify(event,raw,tool):
    if event=='PostToolUseFailure':return 'failed',None,'native-failure'
    if event!='PostToolUse':return 'unknown',None,'not-finished'
    response=raw.get('tool_response',raw.get('toolResponse'))
    shell=tool.lower() in SHELL
    if any(raw.get(k) is True for k in ('isError','is_error','failed')):
        return 'failed',None,'error-flag'
    if not isinstance(response,dict):
        return ('unknown',None,'exit-not-reported') if shell else ('success',None,'completed-non-shell')
    codes=[];invalid=False
    failed=any(response.get(k) is True for k in ('isError','is_error','failed'))
    for key in ('exit_code','exitCode'):
        if key in response and response[key] is not None:
            code=exit_code(response[key])
            if code is None:invalid=True
            else:codes.append(code)
    source='structured-exit'
    if shell:
        # Accept complete code-mode result objects, never regexes inside command output.
        blocks=response.get('content')
        for block in blocks[:10] if isinstance(blocks,list) else []:
            text=block.get('text') if isinstance(block,dict) else None
            if not isinstance(text,str) or len(text)>128*1024:continue
            try:d=json.loads(text)
            except (ValueError,RecursionError):continue
            if not isinstance(d,dict) or not isinstance(d.get('output'),str):continue
            wall=d.get('wall_time_seconds')
            if isinstance(wall,bool) or not isinstance(wall,(float,int)) or not math.isfinite(wall) or wall<0:continue
            code=exit_code(d.get('exit_code'))
            if code is not None:codes.append(code);source='code-mode-result'
    if failed:return 'failed',codes[0] if len(set(codes))==1 else None,'error-flag'
    if invalid or len(set(codes))>1:return 'unknown',None,'conflicting-or-invalid-exit'
    if codes:return ('success' if codes[0]==0 else 'failed'),codes[0],source
    if shell:
        running=any(response.get(k) is not None for k in ('session_id','process_id','sessionId'))
        return 'unknown',None,'running-process' if running else 'exit-not-reported'
    return 'success',None,'completed-non-shell'
