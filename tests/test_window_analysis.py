"""Window qualification equals full findings, without routing/formatting queries."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from analytics import findings
from finding_review import reviewed_findings, window_summary
from journal import Journal

SUMMARY_KEYS=('id','provider','kind','occurrences','sessions','evidenceIds')

def fixture_calls():
    calls=[]
    def add(kind,n,**changes):
        c={'id':str(len(calls)), 'provider':'codex','project':kind,'session':kind,
           'turn':str(n%3),'turn_source':'native','actor':'main','paired':True,
           'fingerprint':kind,'template':kind,'category':'remote','operation':'remote.lookup',
           'resource':'','revision':'','outcome':'success','outcomeSource':'native',
           'startedAt':100+n*3,'endedAt':101+n*3,'durationMs':1000,'model':'other'}
        c.update(changes);calls.append(c)
    for n in range(3):add('retry',n,outcome='failed')
    for n in range(4):add('repeat_call',n)
    for n in range(3):add('repeat_read',n,turn='one',category='read',resource='r',revision='v',fingerprint=str(n))
    for t in range(3):
        for n,cat in enumerate(('read','search','test')):
            add('sequence',t*3+n,turn=str(t),category=cat,operation=cat+'.run',fingerprint=str(t*3+n),template=cat)
    for n in range(12):add('template',n,fingerprint=str(n))
    return calls

class WindowAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.j=Journal(Path(self.temp.name)/'state')
    def tearDown(self):self.j.close();self.temp.cleanup()
    def assert_equivalent(self,calls):
        full=findings(self.j,calls)
        small=findings(self.j,calls,summary_only=True)
        self.assertEqual(small,[{k:f[k] for k in SUMMARY_KEYS} for f in full])
        return full
    def test_all_kinds_keep_ids_counts_order_and_overlap(self):
        calls=fixture_calls();full=self.assert_equivalent(calls)
        self.assertEqual({f['kind'] for f in full},{'retry','repeat_call','repeat_read','sequence','template'})
        # Inventory routing and confirmed invocations do not change qualification.
        self.j.import_inventory([{'provider':'codex','id':'fixture','kind':'mcp','category':'remote','status':'available'}])
        self.assert_equivalent(calls)
        for c in calls[::4]:c.update(paired=False,outcome='pending',endedAt=None)
        self.assert_equivalent(calls)
    def test_limit_multiple_lanes_unknowns_and_no_cached_results(self):
        calls=fixture_calls();expanded=[]
        for n in range(8):
            expanded.extend(dict(c,id=f'{n}:{c["id"]}',project=f'{n}:{c["project"]}',
                                 session=f'{n}:{c["session"]}',provider='glm' if n%2 else 'codex') for c in calls)
        self.assertEqual(len(self.assert_equivalent(expanded)),30)
        self.assertEqual(findings(self.j,[],summary_only=True),[])
        for c in expanded:c.update(turn_source='unknown',outcome='unknown')
        self.assert_equivalent(expanded)
    def test_summary_skips_inventory_and_capability_queries(self):
        sql=[];self.j.db.set_trace_callback(sql.append)
        try:self.assertTrue(findings(self.j,fixture_calls(),summary_only=True))
        finally:self.j.db.set_trace_callback(None)
        self.assertEqual(sql,[])
    def test_rechecks_keep_each_provider_project_and_time_window(self):
        calls=fixture_calls();full=findings(self.j,calls)
        baseline={'observedCalls':20,'pairedCalls':20,'knownTurns':3,'unknownOutcomes':0,'qualifies':True,'occurrences':20}
        for n,f in enumerate(full):
            project=next(c['project'] for c in calls if c['id'] in f['evidenceIds'])
            # Different begin/end boundaries must retain their own qualification.
            self.j.db.execute('INSERT INTO finding_review VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (f['id'],'codex',project,f['kind'],'actioned','skill',100+n*3,12,f['title'],f['titleRu'],json.dumps(baseline)))
        self.j.db.commit()
        calls += [dict(c,id='foreign:'+c['id'],provider='glm') for c in list(calls)]
        def full_oracle(j,subset,**ignored):return findings(j,subset)
        with patch('finding_review.time.time',return_value=200):
            optimized=reviewed_findings(self.j,calls)
            with patch('finding_review.findings',side_effect=full_oracle):
                reference=reviewed_findings(self.j,calls)
        self.assertEqual(optimized,reference)
        self.assertEqual(len(optimized),len(full))
        self.assertTrue(any(not r['after']['qualifies'] for r in optimized))
        self.assertEqual(reviewed_findings(self.j,calls,['glm']),[])
    def test_global_finding_cannot_substitute_for_window(self):
        calls=[c for c in fixture_calls() if c['project']=='repeat_call']
        fid=findings(self.j,calls)[0]['id']
        self.assertTrue(window_summary(self.j,calls,fid)['qualifies'])
        # A fourth call outside the half-open window must not satisfy its threshold.
        subset=[c for c in calls if 100<=c['startedAt']<109]
        r=window_summary(self.j,subset,fid)
        self.assertEqual(r['observedCalls'],3);self.assertFalse(r['qualifies']);self.assertIsNone(r['occurrences'])

if __name__=='__main__':unittest.main()
