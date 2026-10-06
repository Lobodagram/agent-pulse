"""Shared conservative projections for numeric counters and public capability labels."""
import math
import re

def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None

def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.:-]{0,100}', value):
        return 'other'
    if re.search(r'(?i)(bcm_|sk-|ghp_|github_pat_|hf_|bearer|token|password|secret)', value):
        return 'other'
    return value
