#!/usr/bin/env python3
"""Compatibility entry for existing source hooks; implementation is a runtime module."""
import sys
from pathlib import Path
if sys.version_info < (3,11):raise SystemExit(0)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hook_bridge import receive, main
if __name__=='__main__':main()
