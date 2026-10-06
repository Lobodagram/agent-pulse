#!/usr/bin/env python3
"""Fail-open, silent local hook. No model context, decisions, network or transcript reading."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from journal import Journal, MAX_INPUT, PROVIDERS
from platform_support import state_directory

def receive(provider,state,stream):
    j=None
    try:
        body=stream.read(MAX_INPUT+1)
        if len(body)>MAX_INPUT:raise ValueError('oversize')
        raw=json.loads(body)
        j=Journal(state);j.record(provider,raw)
        return True
    except Exception:
        try:
            if j:j.reject(provider)
        except Exception:pass
        return False
    finally:
        if j:j.close()

def main():
    a=argparse.ArgumentParser();a.add_argument('--provider',choices=sorted(PROVIDERS),required=True);a.add_argument('--state',type=Path,default=state_directory());x=a.parse_args()
    receive(x.provider,x.state,sys.stdin.buffer)
    # Always exit 0 with empty stdout/stderr: never alter permission or continuation.
if __name__=='__main__':main()
