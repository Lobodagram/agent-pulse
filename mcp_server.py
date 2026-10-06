#!/usr/bin/env python3
"""Opt-in local stdio MCP: bounded read-only journal evidence, no model or native RPC calls."""
import argparse
import json
import sys
from pulse_version import __version__
from journal import Journal, MAX_INPUT
from analytics import report, compare
from platform_support import state_directory
from evidence_pack import evidence_pack
from pathlib import Path
from session_view import session_page
TOOLS=[
 {'name':'pulse_report','description':'Local observed workflow findings and coverage; not exact tool token costs.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'pulse_session','description':'Read a bounded page of sanitized calls. Pass nextCursor back as cursor to continue one fixed snapshot.','inputSchema':{'type':'object','properties':{'sessionId':{'type':'string'},'cursor':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':100}},'required':['sessionId'],'additionalProperties':False}},
 {'name':'pulse_compare','description':'Observational before/after comparison using manually reviewed task labels.','inputSchema':{'type':'object','properties':{'label':{'type':'string'},'before':{'type':'string'},'after':{'type':'string'}},'required':['label','before','after'],'additionalProperties':False}},
 {'name':'pulse_evidence','description':'Bounded local examples and review checklist for one workflow hypothesis; does not execute or create tools.','inputSchema':{'type':'object','properties':{'findingId':{'type':'string'}},'required':['findingId'],'additionalProperties':False}},
 {'name':'pulse_review_pack','description':'Small bilingual Markdown review of collection, tools, hypotheses and manual decisions; read-only, no inference calls.','inputSchema':{'type':'object','properties':{'language':{'type':'string','enum':['en','ru']}},'additionalProperties':False}}]

def dispatch(request,state):
    method=request.get('method');params=request.get('params') or {}
    if method=='initialize':return {'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'agent-pulse-local','version':__version__}}
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
            data['findingReviewsTruncated'] |= len(data['findingReviews'])>10
            data['findingReviews']=data['findingReviews'][:10];data['mcpNamespaces']=data['mcpNamespaces'][:20]
            data['modelHistory']['truncated'] |= len(data['modelHistory']['segments'])>20
            data['modelHistory']['segments']=data['modelHistory']['segments'][-20:]
            for session in data['sessions']:
                session['modelHistory']['truncated'] |= len(session['modelHistory']['segments'])>5
                session['modelHistory']['segments']=session['modelHistory']['segments'][-5:]
        elif name=='pulse_review_pack' and set(args)<={'language'}:
            from review_pack import markdown_pack
            data={'format':'markdown','language':args.get('language','en'),'markdown':markdown_pack(report(j),args.get('language','en')),'localOnly':True}
        elif name=='pulse_evidence' and set(args)=={'findingId'}:data=evidence_pack(j,args['findingId'])
        elif name=='pulse_session' and 'sessionId' in args and set(args)<={'sessionId','cursor','limit'}:
            limit=args.get('limit',50)
            if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=100:raise ValueError('invalid_page_size')
            data=session_page(j,args['sessionId'],args.get('cursor'),limit)
            data['modelHistory']['truncated'] |= len(data['modelHistory']['segments'])>20
            data['modelHistory']['segments']=data['modelHistory']['segments'][-20:]
        elif name=='pulse_compare' and set(args)=={'label','before','after'}:data=compare(j,args['label'],args['before'],args['after'])
        else:raise ValueError('tool_not_allowed')
        text=json.dumps(data,ensure_ascii=False,allow_nan=False)
        if len(text)>65536:
            return {'content':[{'type':'text','text':json.dumps({'error':'report_too_large','hint':'Reduce session page limit or use local CLI export'})}],'isError':True}
        return {'content':[{'type':'text','text':text}],'isError':False}
    finally:j.close()

def serve(state):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
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

def main():
    a=argparse.ArgumentParser();a.add_argument('--state',type=Path,default=state_directory());serve(a.parse_args().state)

if __name__=='__main__':main()
