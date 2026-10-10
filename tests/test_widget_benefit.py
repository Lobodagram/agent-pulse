"""Benefit evidence in isolated state, never a live account or inferred saving."""
import unittest
from efficiency import (efficiency_report,select_widget_comparison,record_task,
                        ingest_usage,widget_lines,compare_tasks)
from tests import test_efficiency as fixture


class WidgetBenefitTests(unittest.TestCase):
    setUp=fixture.EfficiencyTests.setUp
    tearDown=fixture.EfficiencyTests.tearDown
    pair=fixture.EfficiencyTests.pair
    asset=fixture.EfficiencyTests.asset
    task=fixture.EfficiencyTests.task
    # Reuse only fixture construction, not the inherited test suite.
    def summary(self,p='codex'):
        return efficiency_report(self.j)['widgetBenefits'][p]

    def cohorts(self,after_requests=2,complete=True,quality='accepted',model='demo-model'):
        for variant,requests in [('before',4),('after',after_requests)]:
            for i in range(3):
                key=f'{variant}{i}';call=self.pair(key,model=model if variant=='after' else 'demo-model')
                record_task(self.j,dict(provider='codex',taskId=key,label='release-check',variant=variant,criterion='v1',outcome=quality if variant=='after' else 'accepted',callIds=[call]))
                ingest_usage(self.j,dict(provider='codex',sessionId='demo-session',turnId=key,input=requests*100,output=0,cached_input=0,modelRequests=requests,complete=complete))
        select_widget_comparison(self.j,'codex','release-check','before','after')

    def test_no_observations_or_comparison_does_not_claim_zero_saving(self):
        b=self.summary();self.assertIsNone(b['comparison']);self.assertFalse(b['hasObservations'])
        self.assertIsNone(b['subscriptionSavings']);self.assertFalse(b['causalClaim'])
        lines=widget_lines({'benefit':b});self.assertIn('choose a comparison',lines[2]);self.assertNotIn('0%',str(lines))
        self.assertIn('—',lines[-1])

    def test_linked_registry_deduplicates_versions_and_excludes_unlinked(self):
        self.asset();self.asset('v2');self.asset('v3',provider='glm')
        # Synthetic link only; production registration validates observed finding IDs.
        self.j.db.execute("UPDATE asset_version SET finding='demo-finding' WHERE provider='codex'");self.j.db.commit()
        call=self.pair('applied');self.task('applied',[call],assetId='release-helper',version='v1',applied=True)
        b=self.summary();self.assertEqual(b['linkedAssets']['skill'],1);self.assertEqual(b['declaredAppliedTasks'],1)
        self.assertEqual(b['observedInvocations'],0);self.assertEqual(self.summary('glm')['linkedAssets']['skill'],0)

    def test_explicit_pair_and_provider_isolation(self):
        self.cohorts();c=self.summary()['comparison']
        self.assertEqual(c,compare_tasks(self.j,'release-check','before','after','codex'))
        self.assertEqual(c['metrics']['modelRequestsPerAccepted']['reduction'],.5)
        self.assertIsNone(self.summary('glm')['comparison'])
        select_widget_comparison(self.j,'codex');self.assertIsNone(self.summary()['comparison'])

    def test_incomplete_native_usage_does_not_turn_tool_calls_into_model_calls(self):
        self.cohorts(complete=False);m=self.summary()['comparison']['metrics']
        self.assertIsNone(m['modelRequestsPerAccepted']['reduction']);self.assertIsNone(m['tokensPerAccepted']['reduction'])
        self.assertIn('not enough comparable',widget_lines({'benefit':self.summary()})[2])

    def test_worse_and_zero_are_visible(self):
        self.cohorts(after_requests=6)
        self.assertIn('↑50.0%',widget_lines({'benefit':self.summary()})[2])
        self.assertIn('↑50.0%',widget_lines({'benefit':self.summary()},True)[2])

    def test_quality_decline_blocks_widget_percentage(self):
        self.cohorts(quality='failed');m=self.summary()['comparison']['metrics']
        self.assertIsNone(m['modelRequestsPerAccepted']['reduction']);self.assertIn('quality-not-established',m['modelRequestsPerAccepted']['reasons'])

    def test_different_models_block_widget_percentage(self):
        self.cohorts(model='other-model');m=self.summary()['comparison']['metrics']
        self.assertIsNone(m['tokensPerAccepted']['reduction']);self.assertIn('different-cohorts',m['tokensPerAccepted']['reasons'])

    def test_pin_roundtrip_and_invalid_partial_selector(self):
        select_widget_comparison(self.j,'codex','release-check','before','after');self.j.close()
        from journal import Journal
        from pathlib import Path
        self.j=Journal(Path(self.tmp.name)/'state');self.assertEqual(self.summary()['comparison']['before'],'before')
        for args in [('codex','ok',None,'after'),('codex','ok','same','same'),('no-client','ok','before','after')]:
            with self.assertRaises(ValueError):select_widget_comparison(self.j,*args)

    def test_cache_ratio_separate_from_selected_comparison(self):
        self.cohorts();p={'benefit':self.summary(),'localTokenProfile':{'cacheHitRate':.4}}
        lines=widget_lines(p);self.assertIn('50.0%',lines[2]);self.assertIn('40.0%',lines[3]);self.assertIn('partial',lines[3])
        self.assertIsNone(p['benefit']['subscriptionSavings'])

    def test_invocations_deduplicate_and_ignore_unlinked_or_expired_calls(self):
        self.asset();self.j.db.execute("UPDATE asset_version SET finding='demo-finding'");self.j.db.commit()
        call=self.pair('one');self.pair('other')
        session=self.j.calls()[0]['session']
        for ident,scope in [('release-helper',call),('unlinked-helper',call),('release-helper','0'*32)]:
            self.j.db.execute('INSERT OR IGNORE INTO capability_evidence VALUES (?,?,?,?,?,?,?,?)',('codex',session,'one',scope,ident,'skill','invoked',self.at))
        other=self.j.calls()[1]['id']
        self.j.db.execute('INSERT INTO capability_evidence VALUES (?,?,?,?,?,?,?,?)',('codex',session,'other',other,'release-helper','tool','invoked',self.at))
        self.j.db.commit();self.assertEqual(self.summary()['observedInvocations'],1)
        self.assertEqual(self.summary()['declaredAppliedTasks'],0)

    def test_zero_difference_is_not_unknown(self):
        self.cohorts(after_requests=4);self.assertIn('requests 0%',widget_lines({'benefit':self.summary()})[2])

    def test_widget_uses_all_reviewed_rows_not_100_row_preview(self):
        self.asset();self.j.db.execute("UPDATE asset_version SET finding='demo-finding'");self.j.db.commit()
        for i in range(101):self.task(str(i),[self.pair(str(i))],assetId='release-helper',version='v1',applied=True)
        r=efficiency_report(self.j);self.assertTrue(r['tasksTruncated']);self.assertEqual(len(r['tasks']),100)
        self.assertEqual(r['widgetBenefits']['codex']['declaredAppliedTasks'],101)
