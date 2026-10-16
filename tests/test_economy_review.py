import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('economy_review', Path(__file__).resolve().parents[1]/'scripts/economy_review.py')
economy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(economy)


def daily(provider='glm'):
    return {'generatedAt':100,'analysisLimitReached':False,
        'period':{'date':'2026-10-14','utcOffsetMinutes':180,'start':0,'endExclusive':86400},
        'providers':[{'provider':provider,'calls':10,'outcomes':{'success':5,'failed':1,'unknown':3,'pending':1},
        'knownPairedOutcomes':6,'outcomeCoverage':.6,'failureRateAmongKnown':1/6,
        'commandCoverage':[{'calls':8,'classified':3,'unknown':5,'unknownReasons':{'not-recorded':5}}],
        'failures':[{'tool':'Bash','failed':1,'knownOutcomes':6,'failureClasses':{'unknown':1}}], 'candidates':[{'id':'sample','kind':'sequence','occurrences':5,
            'operations':['edit','unknown'],'confidence':'low'}],
        'reviewsRecordedOnDay':{},'helperReceipts':{'runs':2},
        'quota':{'sampleLimitReached':False,'windows':[], 'completeDayConsumption':None},
        'usageUTC':{'date':'2026-10-14','tokens':999}, 'arbitraryPayload':'DO_NOT_COPY'}]}


class EconomyReviewTests(unittest.TestCase):
    def test_uncertain_results_and_candidates_never_become_savings(self):
        result=economy.summarize([daily()]);p=result['providers'][0]
        self.assertEqual(p['outcomes']['unknown'],3)
        self.assertEqual(p['outcomes']['pending'],1)
        self.assertIsNone(result['tokenSavings'])
        self.assertIsNone(result['subscriptionSavings'])
        self.assertFalse(result['acceptedTasksInferred'])
        self.assertFalse(p['candidatePreview'][0]['automationReady'])
        self.assertNotIn('DO_NOT_COPY',repr(result))

    def test_reset_and_capped_quota_stay_unknown(self):
        d=daily();p=d['providers'][0]
        p['quota']['sampleLimitReached']=True
        p['quota']['windows']=[{'bucket':'glm','kind':'primary','durationMinutes':300,
            'consumedPercentagePoints':None, 'first':{'observedAt':0,'remainingPercent':10},
            'last':{'observedAt':3600,'remainingPercent':95},'sameResetWindow':False}]
        result=economy.summarize([d])
        self.assertIsNone(result['providers'][0]['quota']['windows'][0]['consumedPercentagePoints'])
        text=economy.markdown(result)
        self.assertIn('расход между точками: неизвестно',text)
        self.assertIn('Выборка квот усечена',text)

    def test_provider_and_period_boundaries(self):
        for mutate in ('duplicate','offset','day'):
            a,b=daily(),daily('codex')
            if mutate=='duplicate':b=daily()
            elif mutate=='offset':b['period']['utcOffsetMinutes']=120
            else:b['period']['date']='2026-10-13'
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):economy.summarize([a,b])

    def test_comparison_reuses_metric_specific_quality_gates(self):
        comparison={'reasons':['incomplete-usage'],'confidence':'insufficient','metrics':{
            'tokensPerAccepted':{'before':None,'after':None,'reduction':None,
                'reasons':['incomplete-usage'],'confidence':'insufficient'},
            'observedCallsPerAccepted':{'before':10,'after':5,'reduction':.5,
                'reasons':[],'confidence':'observational'}}}
        result=economy.summarize([daily()],{'glm':comparison})
        text=economy.markdown(result)
        self.assertIn('Токены на принятый результат: не оценено',text)
        self.assertIn('Вызовы на принятый результат: снижение 50.0%',text)
        self.assertIsNone(result['subscriptionSavings'])

    def test_repeated_hypotheses_not_added_into_wasted_calls(self):
        d=daily();d['providers'][0]['candidates']*=5
        result=economy.summarize([d]);p=result['providers'][0]
        self.assertEqual(len(p['candidatePreview']),3)
        self.assertEqual(p['calls'],10)
        self.assertTrue(p['candidatesOverlap'])
        self.assertEqual(result['automaticActions'],[])

    def test_collector_routes_are_local_and_bounded(self):
        class Response:stdout=b'{}'
        with patch.object(economy.subprocess,'run',return_value=Response()) as run:
            d,c=economy.collect(Path('/fixture/pulse-collector'),'2026-10-14',180,['codex','glm'])
        self.assertEqual(run.call_count,2)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][1:4],['journal','--action','daily'])
            self.assertEqual(call.kwargs['timeout'],45)
            self.assertTrue(call.kwargs['check'])
        self.assertEqual(c,{})

    def test_invalid_date_and_offset(self):
        for day,offset in [('2026-1-1',180),('2026-02-30',180),('2026-10-14',True),('2026-10-14',900)]:
            with self.subTest(day=day,offset=offset),self.assertRaises(ValueError):economy.validate_period(day,offset)

    def test_account_resource_not_attributed_to_call_or_task(self):
        result=economy.summarize([daily('codex'),daily('glm')])
        self.assertEqual(len(result['providers']),2)
        self.assertEqual(result['providers'][0]['usageUTC']['tokens'],999)
        self.assertNotIn('tokensPerCall',repr(result))
        self.assertFalse(result['completeCoverage'])
        self.assertEqual(result['modelsCalled'],0)


if __name__=='__main__':unittest.main()
