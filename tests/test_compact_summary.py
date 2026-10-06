import unittest
from compact_summary import provider_line,window_label,quota_pages,tray_tooltip
class CompactTests(unittest.TestCase):
    def test_two_windows_and_conservative_rounding(self):
        p={'id':'codex','quotas':[{'durationMinutes':300,'remainingPercent':7.999},{'durationMinutes':10080,'remainingPercent':35.1}]}
        self.assertEqual(provider_line(p),'CODEX 5h 7% · 7d 35%')
        self.assertEqual(provider_line(p,True),'CODEX 5ч 7% · 7д 35%')
    def test_unknown_tokens_are_not_a_percentage(self):
        self.assertEqual(provider_line({'id':'glm','todayTokens':42000,'quotas':[]}),'GLM —')
        self.assertEqual(provider_line({'id':'codex','quotas':[{'remainingPercent':None}]}),'CODEX win —')
    def test_zero_and_invalid_percentage(self):
        for value in (float('nan'),float('inf'),True,-1,101):self.assertNotIn('%',provider_line({'id':'kimi','quotas':[{'remainingPercent':value}]}))
        self.assertIn('0%',provider_line({'id':'kimi','quotas':[{'remainingPercent':0}]}))
    def test_all_selected_providers_remain_reachable(self):
        providers=[{'id':'p'+str(i)} for i in range(13)]
        self.assertEqual(sum(quota_pages(providers),[]),[provider_line(p) for p in providers])
        self.assertEqual(len(quota_pages(providers)),5)
    def test_tooltip_bounded_without_half_cut_provider(self):
        p=[{'id':'qwen','quotas':[{'remainingPercent':100,'durationMinutes':300},{'remainingPercent':50,'durationMinutes':10080}]}]*15
        t=tray_tooltip(p,True);self.assertLessEqual(len(t),127);self.assertIn('+',t);self.assertTrue(all(x=='Agent Pulse' or x.startswith('+') or x.endswith('50%') for x in t.splitlines()))
    def test_labels_and_stale(self):
        self.assertEqual(window_label(1e300),'win');self.assertEqual(window_label(float('inf')),'win')
        self.assertEqual(window_label(45),'45m');self.assertEqual(window_label(1440),'1d');self.assertEqual(window_label(None,True),'окно')
        self.assertEqual(provider_line({'id':'glm','status':'stale'}),'~GLM —')
