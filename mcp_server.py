#!/usr/bin/env python3
"""Local stdio MCP: read-only evidence by default; bounded control is explicit opt-in."""
import argparse
import json
import sys
from pulse_version import __version__
from journal import Journal, MAX_INPUT
from analytics import report, compare
from platform_support import state_directory
from evidence_pack import evidence_pack
from pathlib import Path
from providers import IDS as PROVIDER_IDS
from session_view import session_page
TOOLS=[
 {'name':'pulse_report','description':'Local observed workflow findings and coverage; not exact tool token costs.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'pulse_session','description':'Read a bounded page of sanitized calls. Pass nextCursor back as cursor to continue one fixed snapshot.','inputSchema':{'type':'object','properties':{'sessionId':{'type':'string'},'cursor':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':100}},'required':['sessionId'],'additionalProperties':False}},
 {'name':'pulse_compare','description':'Observational before/after comparison using manually reviewed task labels.','inputSchema':{'type':'object','properties':{'label':{'type':'string'},'before':{'type':'string'},'after':{'type':'string'}},'required':['label','before','after'],'additionalProperties':False}},
 {'name':'pulse_evidence','description':'Bounded local examples and review checklist for one workflow hypothesis; does not execute or create tools.','inputSchema':{'type':'object','properties':{'findingId':{'type':'string'}},'required':['findingId'],'additionalProperties':False}},
 {'name':'pulse_review_pack','description':'Small bilingual Markdown review of collection, tools, hypotheses and manual decisions; read-only, no inference calls.','inputSchema':{'type':'object','properties':{'language':{'type':'string','enum':['en','ru']}},'additionalProperties':False}}]

# Write tools are absent unless the owner explicitly starts --allow-control.
CONTROL_TOOLS=[
 {'name':'pulse_configure','description':'Change only allowlisted local Agent Pulse settings. Requires user instruction; no credentials or native hook changes.','inputSchema':{'type':'object','properties':{'changes':{'type':'object'}},'required':['changes'],'additionalProperties':False}},
 {'name':'pulse_subscription','description':'Record an owner-provided billing date; never infer it from quota reset dates.','inputSchema':{'type':'object','properties':{'provider':{'type':'string'},'date':{'type':'string'},'kind':{'type':'string','enum':['renewal','expiry','none']}},'required':['provider','date','kind'],'additionalProperties':False}},
 {'name':'pulse_review_finding','description':'Record a human-reviewed finding decision. Actioned requires an implemented change; recheck is observational.','inputSchema':{'type':'object','properties':{'findingId':{'type':'string'},'status':{'type':'string','enum':['open','actioned','dismissed']},'reason':{'type':'string','enum':['unspecified','script','skill','mcp','routing','retrieval','fix','not-applicable','duplicate']},'days':{'type':'integer','enum':[1,3,7]}},'required':['findingId','status','reason','days'],'additionalProperties':False}},
 {'name':'pulse_annotate_session','description':'Save a genuinely reviewed task label and outcome; never fabricate accepted work to test analytics.','inputSchema':{'type':'object','properties':{'sessionId':{'type':'string'},'label':{'type':'string'},'variant':{'type':'string'},'outcome':{'type':'string','enum':['accepted','failed','rework','unknown']}},'required':['sessionId','label','variant','outcome'],'additionalProperties':False}}]
TOOLS.append({'name':'pulse_settings','description':'Read allowlisted local settings and manual billing dates. Never returns keys, locators or native client files.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}})

CONTROL_TOOLS[0]['inputSchema']['properties']['changes']={'type':'object','minProperties':1,'additionalProperties':False,'properties':{
 'enabledProviders':{'type':'array','items':{'type':'string','enum':sorted(PROVIDER_IDS)}},
 **{key:{'type':'boolean'} for key in ['localPatterns','localTokens','topmost','menuNumbers','menuFollowActive']},
 'language':{'type':'string','enum':['en','ru']},'widgetScale':{'type':'number','minimum':0.8,'maximum':1},
 'displayMode':{'type':'string','enum':['floating','menu','compact','tray']},'metricMode':{'type':'string','enum':['limits','today']}}}

def dispatch(request,state,allow_control=False):
    method=request.get('method');params=request.get('params') or {}
    if method=='initialize':return {'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'agent-pulse-local','version':__version__}}
    if method=='ping':return {}
    if method=='tools/list':return {'tools':TOOLS+(CONTROL_TOOLS if allow_control else [])}
    if method!='tools/call':raise ValueError('method_not_allowed')
    name=params.get('name');args=params.get('arguments') or {}
    if not isinstance(args,dict):raise ValueError('invalid_arguments')
    if name=='pulse_settings' and not args:
        from agent_control import settings
        data=settings(state)
        return {'content':[{'type':'text','text':json.dumps(data,ensure_ascii=False,allow_nan=False)}],'isError':False}
    if name in {t['name'] for t in CONTROL_TOOLS}:
        if not allow_control:raise ValueError('control_disabled')
        from agent_control import control
        data=control(name,args,state)
        return {'content':[{'type':'text','text':json.dumps(data,ensure_ascii=False,allow_nan=False)}],'isError':False}
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

def serve(state,allow_control=False):
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
            result=dispatch(req,state,allow_control);res={'jsonrpc':'2.0','id':req['id'],'result':result}
        except Exception:
            if not isinstance(locals().get('req'),dict) or 'id' not in req:continue
            res={'jsonrpc':'2.0','id':req['id'],'error':{'code':-32602,'message':'Request not supported or invalid'}}
        sys.stdout.write(json.dumps(res,ensure_ascii=False,allow_nan=False)+'\n');sys.stdout.flush()

def main():
    a=argparse.ArgumentParser();a.add_argument('--state',type=Path,default=state_directory());a.add_argument('--allow-control',action='store_true',help='Opt-in bounded local settings and manual review writes; no keys or native hooks');args=a.parse_args();serve(args.state,args.allow_control)

if __name__=='__main__':main()
