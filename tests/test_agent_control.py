import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import ssl
import agent_control as c
import glm_quota as g
from mcp_server import dispatch
from providers import atomic_json

class AgentControlTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.state=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def call(self,name,args=None,enabled=False):return dispatch({'method':'tools/call','params':{'name':name,'arguments':args or {}}},self.state,enabled)
    def test_default_write_tools_absent_and_refused(self):
        names={t['name'] for t in dispatch({'method':'tools/list'},self.state)['tools']}
        self.assertIn('pulse_settings',names);self.assertNotIn('pulse_configure',names)
        with self.assertRaises(ValueError):self.call('pulse_configure',{'changes':{'language':'ru'}})
        self.assertFalse((self.state/'config.json').exists())
    def test_opt_in_writes_and_read_never_expose_unknown_config_or_secrets(self):
        atomic_json(self.state/'config.json',{'enabledProviders':['codex'],'unknown':'private-canary','nodePath':'private-canary'})
        atomic_json(self.state/'Secrets.json',{'glm':{'api_key':'private-canary'}})
        self.call('pulse_configure',{'changes':{'language':'ru','enabledProviders':['glm','glm'],'metricMode':'today'}},True)
        read=json.loads(self.call('pulse_settings')['content'][0]['text'])
        self.assertEqual(read['config']['enabledProviders'],['glm']);self.assertEqual(read['config']['language'],'ru')
        self.assertNotIn('private-canary',json.dumps(read));self.assertEqual(json.loads((self.state/'config.json').read_text())['unknown'],'private-canary')
        self.call('pulse_subscription',{'provider':'glm','date':'2026-11-01','kind':'renewal'},True)
        self.assertEqual(c.settings(self.state)['subscriptions']['glm']['date'],'2026-11-01')
    def test_invalid_updates_are_atomic(self):
        c.update_settings(self.state,{'language':'en'})
        before=(self.state/'config.json').read_bytes()
        for changes in [{'key':'canary'},{'enabledProviders':['bad']},{'localPatterns':1},{'widgetScale':True},{'widgetScale':float('nan')},{'metricMode':'bad'},{'language':[]},{'displayMode':'bad'},{'language':'ru','localTokens':1},{}]:
            with self.assertRaises((ValueError,TypeError)):c.update_settings(self.state,changes)
            self.assertEqual(before,(self.state/'config.json').read_bytes())
    def test_pasted_key_trim_and_internal_whitespace(self):
        g.save_key(self.state,' \n fixture-glm \r\n');self.assertEqual(g.secrets(self.state)['glm']['api_key'],'fixture-glm')
        with self.assertRaises(ValueError):g.save_key(self.state,'a b')
        g.save_key(self.state,' \n ');self.assertNotIn('glm',g.secrets(self.state))
    def test_error_categories_never_include_messages_or_urls(self):
        errors=[(HTTPError('private',401,'private',{},None),'authentication'),(HTTPError('private',500,'private',{},None),'remote'),(ssl.SSLError('private'),'tls'),(URLError(ssl.SSLCertVerificationError('private')),'tls'),(URLError('private'),'network'),(ValueError('private'),'schema'),(RuntimeError('private'),'unavailable')]
        g.save_key(self.state,'fixture')
        for error,category in errors:
            with patch('providers.get_json',side_effect=error):result=g.collect(self.state)
            self.assertEqual(result['quotaError'],category);self.assertEqual(result['quotas'],[]);self.assertNotIn('private',json.dumps(result))
