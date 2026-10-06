#!/usr/bin/env python3
"""Opt-in Claude statusline bridge. Emits only sanitized counters to Agent Pulse."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from platform_support import state_directory
from providers import claude_statusline, atomic_json

def main():
    try:
        body=sys.stdin.buffer.read(2*1024*1024+1)
        if len(body)>2*1024*1024:raise ValueError('oversize')
        raw=json.loads(body)
        if not isinstance(raw,dict):raise ValueError('invalid')
        p=claude_statusline(raw)
        atomic_json(state_directory()/'imports/claude.json',p)
        limits=' '.join(f"{q['remainingPercent']:.0f}% left" for q in p['quotas'] if q['remainingPercent'] is not None)
        print('Agent Pulse'+(' · '+limits if limits else ' · local context counter'))
    except Exception:print('Agent Pulse · counters unavailable')
if __name__=='__main__':main()
