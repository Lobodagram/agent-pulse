"""Task/asset attribution tests use invented metadata and isolated state only."""
import tempfile
import time
import unittest
from pathlib import Path
from journal import Journal


class EfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.j=Journal(Path(self.tmp.name)/'state');self.at=time.time()-200

    def tearDown(self):
        self.j.close();self.tmp.cleanup()

    def pair(self, key, turn=None, provider='codex', model='demo-model', outcome=0):
        raw={'session_id':'demo-session','turn_id':turn or key,'tool_use_id':key,'tool_name':'Bash','model':model,'cwd':'/invented/project','tool_input':{'command':'python -m unittest'},'timestamp':self.at}
        for event,delta in [('PreToolUse',0),('PostToolUse',1)]:
            self.j.record(provider,dict(raw,hook_event_name=event,timestamp=self.at+delta,tool_response={'exit_code':outcome}))
        self.at+=2
        return self.j.digest('call',[provider,'demo-session',key])

    def asset(self,version='v1',provider='codex'):
        from efficiency import register_asset
        return register_asset(self.j,{'provider':provider,'assetId':'release-helper','version':version,'kind':'skill'})

    def task(self,key,calls,**extra):
        from efficiency import record_task
        return record_task(self.j,dict(taskId=key,provider='codex',label='release-check',variant='before',criterion='checks-v1',outcome='accepted',callIds=calls,**extra))

    def test_new_registry_and_task_roundtrip_no_payload(self):
        from efficiency import efficiency_report
        self.asset();call=self.pair('one');self.task('task-one',[call],assetId='release-helper',version='v1',applied=True)
        report=efficiency_report(self.j);card=report['assets'][0]
        self.assertEqual(card['tasks'],1);self.assertEqual(card['accepted'],1)
        self.assertEqual(card['declaredUses'],1);self.assertEqual(card['nativeUses'],0)
        self.assertIsNone(card['tokensPerAccepted']);self.assertIsNone(card['subscriptionSavings'])
        self.assertEqual(report['tasks'][0]['callIds'],[call])

    def test_legacy_tasks_keep_unknown_eligibility_after_reopen(self):
        from efficiency import efficiency_report
        self.asset();call=self.pair('one');self.task('task-one',[call],assetId='release-helper',version='v1',applied=True)
        self.j.db.execute('DROP TABLE task_eligibility');self.j.db.commit();self.j.close()
        self.j=Journal(Path(self.tmp.name)/'state')
        card=efficiency_report(self.j)['assets'][0]
        self.assertIsNone(card['eligibleTasks']);self.assertIsNone(card['adoptionRate'])
        self.assertEqual(card['eligibilityUnknownTasks'],1);self.assertEqual(card['lifecycle'],'accepted-awaiting-comparison')

    def test_adoption_uses_only_explicit_eligible_selected_tasks(self):
        from efficiency import efficiency_report
        self.asset();self.asset('v2')
        for key,eligibility,applied,reason in [('a','yes',True,''),('b','yes',False,'unavailable'),('c','no',False,'workflow-mismatch'),('d','unknown',False,'')]:
            self.task(key,[self.pair(key)],assetId='release-helper',version='v1',eligibility=eligibility,applied=applied,nonUseReason=reason)
        report=efficiency_report(self.j);card=next(r for r in report['assets'] if r['version']=='v1')
        self.assertEqual(card['eligibleTasks'],2);self.assertEqual(card['adoptionRate'],.5)
        self.assertEqual(card['nonUseReasons'],{'unavailable':1});self.assertEqual(card['eligibilityKnownTasks'],3)
        self.assertIsNone(next(r for r in report['assets'] if r['version']=='v2')['adoptionRate'])
        self.assertIsNone(card['subscriptionSavings']);self.assertFalse(card['causalClaim'])

    def test_unassessed_application_blocks_adoption_not_zero(self):
        from efficiency import efficiency_report
        self.asset();call=self.pair('one');self.task('one',[call],assetId='release-helper',version='v1',eligibility='yes')
        card=efficiency_report(self.j)['assets'][0]
        self.assertEqual(card['eligibleTasks'],1);self.assertEqual(card['adoptionKnownTasks'],0);self.assertIsNone(card['adoptionRate'])
        self.task('one',[call],assetId='release-helper',version='v1',nonUseReason='unknown')
        card=efficiency_report(self.j)['assets'][0]
        self.assertEqual(card['adoptionRate'],0);self.assertEqual(card['nonUseReasons'],{'unknown':1})

    def test_partial_updates_preserve_assessment_and_contradictions_rollback(self):
        from efficiency import efficiency_report
        self.asset();call=self.pair('one');spec=dict(assetId='release-helper',version='v1')
        self.task('one',[call],**spec,eligibility='no',nonUseReason='workflow-mismatch')
        with self.assertRaisesRegex(ValueError,'contradictory_application'):self.task('one',[call],**spec,applied=True)
        row=efficiency_report(self.j)['tasks'][0]
        self.assertEqual(row['applied'],0);self.assertEqual(row['eligibility'],'no')
        self.task('one',[call],**spec,eligibility='yes')
        self.assertEqual(efficiency_report(self.j)['tasks'][0]['nonUseReason'],'workflow-mismatch')
        self.task('one',[call],**spec,applied=True,nonUseReason='')
        self.assertEqual(efficiency_report(self.j)['assets'][0]['adoptionRate'],1)

    def test_invalid_assessments_do_not_write_and_require_version(self):
        self.asset();call=self.pair('one')
        for extra in [dict(eligibility=[]),dict(nonUseReason={}),dict(eligibility='maybe'),dict(nonUseReason='private note'),dict(eligibility='yes'),dict(nonUseReason='unknown')]:
            with self.assertRaises(ValueError):self.task('one',[call],**extra)
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM reviewed_task').fetchone()[0],0)
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM task_eligibility').fetchone()[0],0)

    def test_assessment_retention_tracks_task_retention(self):
        self.asset();self.task('one',[self.pair('one')],assetId='release-helper',version='v1',eligibility='yes')
        self.j.db.execute('UPDATE reviewed_task SET at=?',(time.time()-31*86400,));self.j.db.commit();self.j.prune()
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM task_eligibility').fetchone()[0],0)

    def test_overlap_rejected_and_re_review_does_not_duplicate(self):
        from efficiency import efficiency_report,record_task
        call=self.pair('one');self.task('task-one',[call]);self.task('task-one',[call])
        with self.assertRaises(ValueError):self.task('task-two',[call])
        self.assertEqual(efficiency_report(self.j)['totalTasks'],1)
        with self.assertRaises(ValueError):record_task(self.j,{'provider':'codex','taskId':'bad','label':'secret user text','variant':'after','criterion':'v1','outcome':'accepted','callIds':[call]})

    def test_full_turn_usage_and_cache_are_not_double_counted(self):
        from efficiency import efficiency_report
        self.asset();a=self.pair('one',turn='t');b=self.pair('two',turn='t')
        self.j.usage('codex','demo-session','t',{'input':100,'cached_input':80,'output':20},complete=True)
        self.task('task-one',[a,b],assetId='release-helper',version='v1',applied=True)
        card=efficiency_report(self.j)['assets'][0]
        self.assertEqual(card['tokensPerAccepted'],120);self.assertEqual(card['cacheHitRate'],.8)
        self.assertIsNone(card['modelRequests']);self.assertEqual(card['usageCompleteTasks'],1)

    def test_split_turn_and_conflicting_counters_block_savings(self):
        from efficiency import efficiency_report
        self.asset();a=self.pair('one',turn='t');self.pair('two',turn='t')
        self.j.usage('codex','demo-session','t',{'input':100,'cached_input':80,'output':20},complete=True)
        self.task('task-one',[a],assetId='release-helper',version='v1',applied=True)
        card=efficiency_report(self.j)['assets'][0];self.assertIsNone(card['tokensPerAccepted'])
        self.assertEqual(card['usageCompleteTasks'],0)

    def test_all_attempts_cost_including_failed_and_unreviewed(self):
        from efficiency import efficiency_report,record_task
        self.asset()
        for i,outcome in enumerate(['accepted','failed','unknown']):
            key='c'+str(i);c=self.pair(key);self.j.usage('codex','demo-session',key,{'input':100,'cached_input':0,'output':20},complete=True)
            record_task(self.j,{'provider':'codex','taskId':'task-'+key,'label':'release-check','variant':'after','criterion':'checks-v1','outcome':outcome,'callIds':[c],'assetId':'release-helper','version':'v1','applied':True})
        card=efficiency_report(self.j)['assets'][0]
        self.assertEqual(card['tokensPerAccepted'],360);self.assertEqual(card['reviewed'],2)
        self.assertEqual(card['acceptanceRate'],.5)

    def test_provider_and_version_isolation(self):
        from efficiency import record_task
        self.asset(provider='glm');call=self.pair('one')
        with self.assertRaises(ValueError):self.task('task-one',[call],assetId='release-helper',version='v1')
        with self.assertRaises(ValueError):record_task(self.j,{'provider':'glm','taskId':'task-one','label':'release-check','variant':'after','criterion':'v1','outcome':'accepted','callIds':[call]})

    def test_missing_late_calls_invalidate_frozen_selection(self):
        from efficiency import efficiency_report
        self.asset();c=self.pair('one',turn='t');self.j.usage('codex','demo-session','t',{'input':100,'cached_input':0,'output':20},complete=True)
        self.task('task-one',[c],assetId='release-helper',version='v1');self.pair('late',turn='t')
        self.assertIsNone(efficiency_report(self.j)['assets'][0]['tokensPerAccepted'])

    def test_comparison_requires_matching_models_and_quality(self):
        from efficiency import compare_tasks,record_task
        for variant,model in [('before','demo-a'),('after','demo-b')]:
            for i in range(3):
                key=variant+str(i);c=self.pair(key,model=model)
                self.j.usage('codex','demo-session',key,{'input':100,'cached_input':0,'output':20},complete=True)
                record_task(self.j,{'provider':'codex','taskId':key,'label':'release-check','variant':variant,'criterion':'v1','outcome':'accepted','callIds':[c]})
        result=compare_tasks(self.j,'release-check','before','after')
        self.assertIsNone(result['tokenReduction']);self.assertFalse(result['causalClaim'])
        self.assertIn('different-cohorts',result['reasons'])

    def test_operational_comparison_does_not_need_token_counters(self):
        from efficiency import compare_tasks,record_task
        for variant,count in [('before',2),('after',1)]:
            for i in range(3):
                key=variant+str(i);calls=[self.pair(key+str(n),turn=key) for n in range(count)]
                record_task(self.j,{'provider':'codex','taskId':key,'label':'release-check','variant':variant,'criterion':'v1','outcome':'accepted','callIds':calls})
        value=compare_tasks(self.j,'release-check','before','after')
        self.assertIsNone(value['tokenReduction']);self.assertIn('incomplete-usage',value['reasons'])
        self.assertEqual(value['metrics']['observedCallsPerAccepted']['reduction'],.5)
        self.assertAlmostEqual(value['metrics']['elapsedMsPerAccepted']['reduction'],2/3)
        self.assertIsNone(value['metrics']['modelRequestsPerAccepted']['reduction'])

    def test_operational_comparison_still_blocks_quality_decline(self):
        from efficiency import compare_tasks,record_task
        for variant in ['before','after']:
            for i in range(3):
                key=variant+str(i);call=self.pair(key)
                record_task(self.j,{'provider':'codex','taskId':key,'label':'release-check','variant':variant,'criterion':'v1','outcome':'failed' if variant=='after' and i==0 else 'accepted','callIds':[call]})
        value=compare_tasks(self.j,'release-check','before','after')
        for metric in value['metrics'].values():
            self.assertIsNone(metric['reduction']);self.assertIn('quality-not-established',metric['reasons'])

    def test_request_comparison_with_zero_baseline_is_not_infinite_saving(self):
        from efficiency import compare_tasks,record_task
        for variant in ['before','after']:
            for i in range(3):
                key=variant+str(i);call=self.pair(key)
                self.j.usage('codex','demo-session',key,{},complete=True,model_requests=0 if variant=='before' else 1)
                record_task(self.j,{'provider':'codex','taskId':key,'label':'release-check','variant':variant,'criterion':'v1','outcome':'accepted','callIds':[call]})
        metric=compare_tasks(self.j,'release-check','before','after')['metrics']['modelRequestsPerAccepted']
        self.assertIsNone(metric['reduction']);self.assertIn('zero-baseline',metric['reasons'])

    def test_comparable_observations_allow_difference_without_causal_claim(self):
        from efficiency import compare_tasks,record_task
        for variant,tokens in [('before',200),('after',100)]:
            for i in range(3):
                key=variant+str(i);call=self.pair(key)
                self.j.usage('codex','demo-session',key,{'input':tokens,'cached_input':0,'output':0},complete=True,model_requests=1)
                record_task(self.j,{'provider':'codex','taskId':key,'label':'release-check','variant':variant,'criterion':'v1','outcome':'accepted','callIds':[call]})
        value=compare_tasks(self.j,'release-check','before','after','codex')
        self.assertEqual(value['tokenReduction'],.5);self.assertEqual(value['confidence'],'observational')
        self.assertFalse(value['causalClaim']);self.assertIsNone(value['subscriptionSavings'])
        self.assertEqual(value['groups']['after']['modelRequests'],3)

    def test_conflicting_receipts_and_expired_reviews_are_not_complete(self):
        from efficiency import efficiency_report
        self.asset();call=self.pair('one');self.task('task-one',[call],assetId='release-helper',version='v1')
        self.j.usage('codex','demo-session','one',{'input':100,'cached_input':0,'output':20},complete=True)
        self.j.usage('codex','demo-session','one',{'input':200,'cached_input':0,'output':20},source='second-reporter',complete=True)
        card=efficiency_report(self.j)['assets'][0]
        self.assertIsNone(card['tokensPerAccepted']);self.assertEqual(card['usageCompleteTasks'],0)
        self.j.db.execute('UPDATE reviewed_task SET at=?',(time.time()-31*86400,));self.j.db.commit()
        self.assertEqual(efficiency_report(self.j)['totalTasks'],0)

    def test_usage_update_is_atomic_if_status_write_fails(self):
        self.j.usage('codex','demo-session','one',{'input':100,'output':20},complete=True)
        self.j.db.execute("CREATE TRIGGER reject_usage BEFORE INSERT ON turn_usage_status BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):self.j.usage('codex','demo-session','one',{'input':200,'output':20},complete=False)
        self.assertEqual(self.j.db.execute('SELECT input FROM turn_usage').fetchone()[0],100)
        self.assertEqual(self.j.db.execute('SELECT complete FROM turn_usage_status').fetchone()[0],1)

    def test_model_requests_do_not_depend_on_token_availability(self):
        from efficiency import ingest_usage,efficiency_report
        self.asset();call=self.pair('one');self.task('task-one',[call],assetId='release-helper',version='v1')
        ingest_usage(self.j,{'provider':'codex','sessionId':'demo-session','turnId':'one','modelRequests':2,'complete':True})
        card=efficiency_report(self.j)['assets'][0]
        self.assertEqual(card['modelRequests'],2);self.assertIsNone(card['tokensPerAccepted'])

    def test_completeness_does_not_merge_incomplete_sources(self):
        from efficiency import efficiency_report
        self.asset();call=self.pair('one');self.task('task-one',[call],assetId='release-helper',version='v1')
        self.j.usage('codex','demo-session','one',{'input':100},complete=True)
        self.j.usage('codex','demo-session','one',{'output':20},source='second-reporter')
        self.assertIsNone(efficiency_report(self.j)['assets'][0]['tokensPerAccepted'])

    def test_cache_subset_is_checked_per_turn_not_just_group_total(self):
        from efficiency import efficiency_report
        self.asset();a=self.pair('one');b=self.pair('two')
        self.j.usage('codex','demo-session','one',{'input':100,'output':20},complete=True)
        self.j.usage('codex','demo-session','one',{'cached_input':200},source='second-reporter')
        self.j.usage('codex','demo-session','two',{'input':1000,'output':20,'cached_input':0},complete=True)
        self.task('task-one',[a,b],assetId='release-helper',version='v1')
        self.assertIsNone(efficiency_report(self.j)['assets'][0]['cacheHitRate'])

    def test_receipts_are_explicit_and_control_writes_are_opt_in(self):
        from efficiency import ingest_usage,efficiency_report
        from mcp_server import dispatch
        spec={'provider':'codex','assetId':'release-helper','version':'1.0.0','kind':'mcp'}
        request={'method':'tools/call','params':{'name':'pulse_register_asset','arguments':spec}}
        with self.assertRaises(ValueError):dispatch(request,self.j.state)
        self.assertFalse(dispatch(request,self.j.state,allow_control=True)['isError'])
        for bad in [{'input':True},{'input':-1},{'input':1,'complete':'yes'},{'input':1,'modelRequests':1.5},{'input':1,'prompt':'PRIVATE_CANARY'},{'input':1,'source':'verified'}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):ingest_usage(self.j,dict(provider='codex',sessionId='demo-session',turnId='t',**bad))
        ingest_usage(self.j,{'provider':'codex','sessionId':'PRIVATE_SESSION_CANARY','turnId':'PRIVATE_TURN_CANARY','input':100,'output':20,'complete':True})
        self.assertNotIn('PRIVATE_',str(efficiency_report(self.j)))
        self.assertNotIn('PRIVATE_',str([dict(r) for r in self.j.db.execute('SELECT * FROM turn_usage')]))

    def test_version_identity_cannot_change_and_operation_routing_is_specific(self):
        from efficiency import register_asset
        self.asset()
        with self.assertRaises(ValueError):register_asset(self.j,{'provider':'codex','assetId':'release-helper','version':'v1','kind':'mcp'})
        with self.assertRaises(ValueError):register_asset(self.j,{'provider':'codex','assetId':'release-helper','version':'v1','kind':'skill','operations':['ci_logs']})

    def test_parallel_reviews_cannot_claim_the_same_call(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from efficiency import record_task,efficiency_report
        call=self.pair('one');barrier=Barrier(2)
        def writer(key):
            j=Journal(self.j.state)
            original=j.calls
            def observed():
                calls=original();barrier.wait(timeout=5);return calls
            j.calls=observed
            try:
                record_task(j,{'provider':'codex','taskId':key,'label':'release-check','variant':'after','criterion':'v1','outcome':'accepted','callIds':[call]})
                return 'saved'
            except ValueError as error:return str(error)
            finally:j.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(writer,['first','second']))
        self.assertEqual(sorted(results),['overlapping_task','saved'])
        self.assertEqual(efficiency_report(self.j)['totalTasks'],1)

    def test_legacy_comparison_is_not_limited_to_100_session_preview(self):
        from analytics import compare,report
        for i in range(103):
            sid='invented-session-'+str(i)
            raw={'session_id':sid,'turn_id':'one','tool_use_id':'one','tool_name':'Read','timestamp':time.time()-1000+i,'cwd':'/invented/project'}
            self.j.record('codex',dict(raw,hook_event_name='PreToolUse'))
            self.j.record('codex',dict(raw,hook_event_name='PostToolUse'))
            if i<3:self.j.annotate(self.j.digest('session',['codex',sid]),'release-check','accepted','before')
        self.assertTrue(report(self.j)['sessionsTruncated'])
        self.assertEqual(compare(self.j,'release-check','before','after')['groups']['before']['sessions'],3)
