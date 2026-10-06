"""A bounded local review brief, never a generated skill or automatic optimization."""
import re
from analytics import report

def evidence_pack(j,finding_id):
    if not isinstance(finding_id,str) or not re.fullmatch('[a-f0-9]{32}',finding_id):raise ValueError('invalid_finding')
    r=report(j)
    finding=next((f for f in r['findings'] if f['id']==finding_id),None)
    if not finding:raise ValueError('finding_not_found')
    ids=set(finding['evidenceIds']);calls=[c for c in j.calls() if c['id'] in ids]
    return {'schemaVersion':1,'localOnly':True,'finding':finding,'calls':calls,
            'quality':r['quality'],
            'review':{'status':'hypothesis, not approved automation',
                      'nextAction':finding['action'],
                      'steps':['Check that the sampled calls solve the same task.',
                               'Review native coverage and unknown or incomplete outcomes.',
                               'Confirm live availability and actual capability use.',
                               'Choose a small script, skill or typed MCP only after review.',
                               'Compare accepted results and rework on comparable before/after tasks.'],
                      'tokenSavings':None,'autoExecute':False}}
