"""Project result metadata only. Shell stdout is never evidence of an exit code."""
import json
import math

SHELL = {'bash','shell','exec_command','functions.exec_command','functions.exec','exec','terminal','write_stdin','functions.write_stdin'}

ERROR_CLASSES = {'SyntaxError':'syntax', 'ReferenceError':'reference', 'TypeError':'type',
                 'RangeError':'range', 'TimeoutError':'timeout', 'EACCES':'permission',
                 'EPERM':'permission', 'ENOENT':'not-found', 'MODULE_NOT_FOUND':'module-not-found',
                 'ERR_MODULE_NOT_FOUND':'module-not-found', 'ECONNREFUSED':'connection', 'ETIMEDOUT':'timeout'}


def failure_class(raw, tool):
    """Fixed reported categories only. Neither messages nor stack traces survive."""
    response=raw.get('tool_response',raw.get('toolResponse'))
    containers=[raw]
    if isinstance(response,dict):
        containers.append(response)
        if isinstance(response.get('structuredContent'),dict):containers.append(response['structuredContent'])
    labels=set()
    for container in containers:
        error=container.get('error')
        if not isinstance(error,dict):continue
        for key in ('name','type','code'):
            value=error.get(key)
            if isinstance(value,str) and value in ERROR_CLASSES:labels.add(ERROR_CLASSES[value])
    if len(labels)>1:return 'conflicting','reported-structured'
    if labels:return next(iter(labels)),'reported-structured'
    # For non-shell failed tools, accept only a fixed exception header at byte zero.
    # Never search arbitrary stdout or classify a successful response by its text.
    if tool.lower() not in SHELL and isinstance(response,dict):
        blocks=response.get('content')
        if isinstance(blocks,list) and len(blocks)<=10:
            for block in blocks:
                value=block.get('text') if isinstance(block,dict) else None
                if not isinstance(value,str) or len(value)>4096:continue
                for name,label in ERROR_CLASSES.items():
                    if value.startswith(name+':'):labels.add(label)
    if len(labels)>1:return 'conflicting','reported-prefix'
    return (next(iter(labels)),'reported-prefix') if labels else ('unknown','unreported')

def exit_code(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and -255<=value<=255 else None


def value_kind(value):
    if value is None:return 'null'
    if isinstance(value,dict):return 'object'
    if isinstance(value,str):return 'string'
    if isinstance(value,list):return 'array'
    return 'other'


def exit_field_state(container):
    if not isinstance(container,dict):return 'not-object'
    values=[container[k] for k in ('exit_code','exitCode') if k in container]
    if not values:return 'absent'
    actual=[v for v in values if v is not None]
    if not actual:return 'null'
    if any(exit_code(v) is None for v in actual):return 'invalid'
    return 'valid' if len(set(actual))==1 else 'conflicting'


def response_evidence(raw,tool,status):
    """Fixed envelope types and field states; no arbitrary keys, values or output."""
    key='tool_response' if 'tool_response' in raw else 'toolResponse' if 'toolResponse' in raw else None
    response=raw.get(key) if key else None
    structured=response.get('structuredContent') if isinstance(response,dict) else None
    blocks=response.get('content') if isinstance(response,dict) else None
    flag=any(c.get(k) is True for c in [raw]+([response] if isinstance(response,dict) else [])+
             ([structured] if isinstance(structured,dict) else []) for k in ('isError','is_error','failed'))
    text_count=0;wrappers=0;limited=isinstance(blocks,list) and len(blocks)>10
    for block in blocks[:10] if isinstance(blocks,list) else []:
        text=block.get('text') if isinstance(block,dict) else None
        if not isinstance(text,str):continue
        text_count+=1
        if len(text)>128*1024:limited=True;continue
        try:value=json.loads(text)
        except (ValueError,RecursionError):continue
        if not isinstance(value,dict) or not isinstance(value.get('output'),str):continue
        wall=value.get('wall_time_seconds')
        if isinstance(wall,bool) or not isinstance(wall,(float,int)) or not math.isfinite(wall) or wall<0:continue
        wrappers+=1
    failure_source=failure_class(raw,tool)[1] if status=='failed' else 'not-failure'
    return {'responseKind':value_kind(response) if key else 'missing',
        'structuredKind':value_kind(structured) if isinstance(response,dict) and 'structuredContent' in response else 'missing',
        'directExit':exit_field_state(response),'structuredExit':exit_field_state(structured),
        'errorFlag':flag,'contentKind':value_kind(blocks) if isinstance(response,dict) and 'content' in response else 'missing',
        'contentItems':min(len(blocks),11) if isinstance(blocks,list) else 0,
        'textBlocksInspected':text_count,'codeModeWrappers':wrappers,'contentLimitReached':limited,
        'failureCategorySource':failure_source}


def stored_response_evidence(serialized):
    """Only fixed projected labels survive corruption or manual input."""
    if not isinstance(serialized,str) or len(serialized)>2048:return None
    try:data=json.loads(serialized)
    except (ValueError,RecursionError):return None
    if not isinstance(data,dict):return None
    kinds={'missing','null','object','string','array','other'}
    exits={'not-object','absent','null','valid','invalid','conflicting'}
    labels={'responseKind':kinds,'structuredKind':kinds,'directExit':exits,'structuredExit':exits,
            'contentKind':kinds,'failureCategorySource':{'reported-structured','reported-prefix','unreported','not-failure'}}
    counts={'contentItems':11,'textBlocksInspected':10,'codeModeWrappers':10}
    bools={'errorFlag','contentLimitReached'}
    if set(data)!=set(labels)|set(counts)|bools:return None
    if any(not isinstance(data[k],str) or data[k] not in values for k,values in labels.items()):return None
    if any(type(data[k]) is not int or not 0<=data[k]<=limit for k,limit in counts.items()):return None
    if any(type(data[k]) is not bool for k in bools):return None
    return data

def classify(event,raw,tool):
    if event=='PostToolUseFailure':return 'failed',None,'native-failure'
    if event!='PostToolUse':return 'unknown',None,'not-finished'
    response=raw.get('tool_response',raw.get('toolResponse'))
    shell=tool.lower() in SHELL
    if any(raw.get(k) is True for k in ('isError','is_error','failed')):
        return 'failed',None,'error-flag'
    if not isinstance(response,dict):
        return ('unknown',None,'exit-not-reported') if shell else ('success',None,'completed-non-shell')
    codes=[];invalid=False;limit_exceeded=False
    failed=any(response.get(k) is True for k in ('isError','is_error','failed'))
    for key in ('exit_code','exitCode'):
        if key in response and response[key] is not None:
            code=exit_code(response[key])
            if code is None:invalid=True
            else:codes.append(code)
    # MCP structuredContent is a typed envelope; never parse arbitrary stdout.
    structured=response.get('structuredContent')
    if shell and isinstance(structured,dict):
        for key in ('exit_code','exitCode'):
            if key in structured and structured[key] is not None:
                code=exit_code(structured[key])
                if code is None:invalid=True
                else:codes.append(code)
        failed |= any(structured.get(k) is True for k in ('isError','is_error','failed'))
    source='structured-exit'
    if shell:
        # Accept complete code-mode result objects, never regexes inside command output.
        blocks=response.get('content')
        # A bounded prefix cannot establish success: a later block may contradict it.
        limit_exceeded=isinstance(blocks,list) and len(blocks)>10
        for block in blocks[:10] if isinstance(blocks,list) else []:
            text=block.get('text') if isinstance(block,dict) else None
            if not isinstance(text,str):continue
            if len(text)>128*1024:limit_exceeded=True;continue
            try:d=json.loads(text)
            except (ValueError,RecursionError):continue
            if not isinstance(d,dict) or not isinstance(d.get('output'),str):continue
            wall=d.get('wall_time_seconds')
            if isinstance(wall,bool) or not isinstance(wall,(float,int)) or not math.isfinite(wall) or wall<0:continue
            code=exit_code(d.get('exit_code'))
            if d.get('exit_code') is not None and code is None:invalid=True
            if code is not None:codes.append(code);source='code-mode-result'
    if failed:return 'failed',codes[0] if len(set(codes))==1 else None,'error-flag'
    if limit_exceeded:return 'unknown',None,'result-limit-exceeded'
    if invalid or len(set(codes))>1:return 'unknown',None,'conflicting-or-invalid-exit'
    if codes:return ('success' if codes[0]==0 else 'failed'),codes[0],source
    if shell:
        running=any(response.get(k) is not None or isinstance(structured,dict) and structured.get(k) is not None for k in ('session_id','process_id','sessionId'))
        return 'unknown',None,'running-process' if running else 'exit-not-reported'
    return 'success',None,'completed-non-shell'
