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
        lines=widget_lines({'benefit':b});self.assertIn('not evaluated',lines[3]);self.assertNotIn('0%',str(lines))
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
        self.assertIn('insufficient evidence',widget_lines({'benefit':self.summary()})[3])

    def test_worse_and_zero_are_visible(self):
        self.cohorts(after_requests=6)
        self.assertIn('↑50.0%',widget_lines({'benefit':self.summary()})[3])
        self.assertIn('↑50.0%',widget_lines({'benefit':self.summary()},True)[3])

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
        lines=widget_lines(p);self.assertIn('50.0%',lines[3]);self.assertIn('40.0%',lines[4]);self.assertIn('Model cache',lines[4]);self.assertIn('partial',lines[4])
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
        self.cohorts(after_requests=4);self.assertIn('requests 0%',widget_lines({'benefit':self.summary()})[3])

    def native(self,key,tool,args,provider='glm',success=True):
        raw={'session_id':'activity-fixture','turn_id':key,'tool_use_id':key,'tool_name':tool,
             'tool_input':args,'timestamp':self.at,'cwd':'/invented/project'}
        self.j.record(provider,dict(raw,hook_event_name='PreToolUse'))
        event='PostToolUse' if success else 'PostToolUseFailure'
        self.j.record(provider,dict(raw,hook_event_name=event,timestamp=self.at+1,tool_response={}))
        self.at+=2

    def test_unlinked_observed_activity_is_visible_without_fabricated_effect(self):
        self.j.import_inventory([{'provider':'codex','id':'fixture-skill','kind':'skill',
                                 'category':'test','status':'configured','locator':'/invented/skill/SKILL.md'}])
        self.native('known','Skill',{'skill':'fixture-skill'})
        self.native('unknown','Skill',{'skill':'PRIVATE_UNKNOWN'})
        self.native('read','Read',{'file_path':'/invented/skill/SKILL.md'})
        self.native('mcp','mcp__fixture__inspect',{})
        b=self.summary('glm');a=b['activity']
        self.assertEqual((a['skillCalls'],a['matchedSkillCalls'],a['unmatchedSkillCalls'],a['skillReads'],a['mcpCalls']),(2,1,1,1,1))
        self.assertEqual(sum(b['linkedAssets'].values()),0);self.assertEqual(b['observedInvocations'],0)
        self.assertEqual(b['improvementEvaluationState'],'no-linked-improvements')
        lines=widget_lines({'benefit':b},True)
        self.assertIn('Skill 2',lines[0]);self.assertIn('чтения 1',lines[0]);self.assertIn('MCP-вызовы 1',lines[1])
        self.assertIn('ещё не учтены',lines[2]);self.assertIn('ещё не оценён',lines[3])
        self.assertNotIn('PRIVATE_UNKNOWN',str(b));self.assertIsNone(b['subscriptionSavings'])
        self.assertFalse(a['nonUseEstablished']);self.assertEqual(self.summary('codex')['activity']['observedCalls'],0)

    def test_linked_but_unreviewed_is_waiting_not_zero_application(self):
        self.asset();self.j.db.execute("UPDATE asset_version SET finding='demo-finding'");self.j.db.commit()
        self.pair('ordinary')
        b=self.summary();self.assertEqual(b['improvementEvaluationState'],'awaiting-task-review')
        lines=widget_lines({'benefit':b},True)
        self.assertIn('учтено 1',lines[2]);self.assertIn('ждём оценку',lines[2]);self.assertNotIn('применений 0',str(lines))

    def test_failed_skill_is_activity_not_successful_application(self):
        self.native('failed','Skill',{'skill':'PRIVATE_UNKNOWN'},success=False)
        a=self.summary('glm')['activity']
        self.assertEqual(a['skillCalls'],1);self.assertEqual(a['successfulSkillCalls'],0)
        self.assertEqual(a['unmatchedSkillCalls'],0)

    def test_helpers_are_visible_without_native_calls_and_isolated_by_provider(self):
        from check_receipts import receipt
        receipt(self.j,{'provider':'glm','runId':'1'*32,'operation':'workflow-check','version':'v1',
                        'startedAt':self.at,'endedAt':self.at+1,'status':'failed'})
        b=self.summary('glm');self.assertFalse(b['hasObservations'])
        self.assertEqual(b['activity']['helperRuns'],1);self.assertEqual(b['activity']['helperKnownResults'],1)
        self.assertIn('helpers 1',widget_lines({'benefit':b})[1])
        self.assertEqual(self.summary('codex')['activity']['helperRuns'],0);self.assertIsNone(b['comparison'])

    def test_legacy_snapshot_reports_missing_activity_instead_of_zero(self):
        b=self.summary();del b['activity']
        lines=widget_lines({'benefit':b})
        self.assertIn('not reported',lines[0]);self.assertIn('not evaluated',lines[3]);self.assertNotIn('Skill 0',str(lines))

    def test_widget_uses_all_reviewed_rows_not_100_row_preview(self):
        self.asset();self.j.db.execute("UPDATE asset_version SET finding='demo-finding'");self.j.db.commit()
        for i in range(101):self.task(str(i),[self.pair(str(i))],assetId='release-helper',version='v1',applied=True)
        r=efficiency_report(self.j);self.assertTrue(r['tasksTruncated']);self.assertEqual(len(r['tasks']),100)
        self.assertEqual(r['widgetBenefits']['codex']['declaredAppliedTasks'],101)
