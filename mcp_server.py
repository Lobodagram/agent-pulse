#!/usr/bin/env python3
"""Opt-in local stdio MCP: bounded read-only journal evidence, no model or native RPC calls."""
import argparse
import json
import sys
from journal import Journal, MAX_INPUT
from analytics import report, compare
from platform_support import state_directory
from evidence_pack import evidence_pack
from pathlib import Path
TOOLS=[
 {'name':'pulse_report','description':'Local observed workflow findings and coverage; not exact tool token costs.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'pulse_session','description':'Read at most 100 sanitized observed calls for one hashed session.','inputSchema':{'type':'object','properties':{'sessionId':{'type':'string'}},'required':['sessionId'],'additionalProperties':False}},
 {'name':'pulse_compare','description':'Observational before/after comparison using manually reviewed task labels.','inputSchema':{'type':'object','properties':{'label':{'type':'string'},'before':{'type':'string'},'after':{'type':'string'}},'required':['label','before','after'],'additionalProperties':False}},
 {'name':'pulse_evidence','description':'Bounded local examples and review checklist for one workflow hypothesis; does not execute or create tools.','inputSchema':{'type':'object','properties':{'findingId':{'type':'string'}},'required':['findingId'],'additionalProperties':False}}]

def dispatch(request,state):
    method=request.get('method');params=request.get('params') or {}
    if method=='initialize':return {'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'agent-pulse-local','version':'0.5.1'}}
    if method=='ping':return {}
    if method=='tools/list':return {'tools':TOOLS}
    if method!='tools/call':raise ValueError('method_not_allowed')
    name=params.get('name');args=params.get('arguments') or {}
    if not isinstance(args,dict):raise ValueError('invalid_arguments')
    j=Journal(state)
    try:
        if name=='pulse_report' and not args:
            data=report(j);data.pop('recentCalls',None);data['sessions']=data['sessions'][:20];data['findings']=data['findings'][:10]
            data['capabilitiesTruncated']=len(data['capabilities'])>20
            data['capabilities']=data['capabilities'][:20];data['toolUsage']=data['toolUsage'][:30];data['crossClientPatterns']=data['crossClientPatterns'][:10]
        elif name=='pulse_evidence' and set(args)=={'findingId'}:data=evidence_pack(j,args['findingId'])
        elif name=='pulse_session' and set(args)=={'sessionId'} and isinstance(args['sessionId'],str):
            import re
            if not re.fullmatch('[a-f0-9]{32}',args['sessionId']):raise ValueError('invalid_session')
            rows=j.calls(args['sessionId']);data={'calls':rows[:100],'truncated':len(rows)>100}
        elif name=='pulse_compare' and set(args)=={'label','before','after'}:data=compare(j,args['label'],args['before'],args['after'])
        else:raise ValueError('tool_not_allowed')
        text=json.dumps(data,ensure_ascii=False,allow_nan=False)
        if len(text)>65536:text=json.dumps({'error':'report_too_large','hint':'Read one session or use local CLI export'})
        return {'content':[{'type':'text','text':text}],'isError':False}
    finally:j.close()

def serve(state):
    while True:
        line=sys.stdin.buffer.readline(MAX_INPUT+1)
        if not line:break
        if len(line)>MAX_INPUT:
            while line and not line.endswith(b'\n'):line=sys.stdin.buffer.readline(MAX_INPUT+1)
            continue
        req=None
        try:
            req=json.loads(line)
            if not isinstance(req,dict) or 'id' not in req:continue
            result=dispatch(req,state);res={'jsonrpc':'2.0','id':req['id'],'result':result}
        except Exception:
            if not isinstance(locals().get('req'),dict) or 'id' not in req:continue
            res={'jsonrpc':'2.0','id':req['id'],'error':{'code':-32602,'message':'Request not supported or invalid'}}
        sys.stdout.write(json.dumps(res,ensure_ascii=False,allow_nan=False)+'\n');sys.stdout.flush()

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--state',type=Path,default=state_directory());serve(a.parse_args().state)
