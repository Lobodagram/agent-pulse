from pathlib import Path
import json
import tempfile
import time
import unittest
from unittest.mock import patch
from journal import Journal, atomic_json
from instrumentation import scan_inventory
from inventory_refresh import load_plans, remember_sources, refresh_inventory, replace_provider, PLAN_FILE


class InventoryRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.j = Journal(self.root/'state')
        self.skills = self.root/'skills'
        self.skill('first-check')

    def tearDown(self):
        self.j.close()
        self.tmp.cleanup()

    def skill(self, name):
        folder = self.skills/name
        folder.mkdir(parents=True)
        (folder/'SKILL.md').write_bytes(b'PRIVATE_INSTRUCTIONS\xff')

    def due(self):
        plans = load_plans(self.j.state)
        plans['glm']['lastAttempt'] = time.time()-3601
        atomic_json(self.j.state/PLAN_FILE, plans)

    def prepare(self):
        replace_provider(self.j, 'glm', scan_inventory('glm', [self.skills]))
        remember_sources(self.j, 'glm', [self.skills])
        self.due()

    def test_refresh_is_opt_in_and_never_discovers_roots(self):
        with patch('inventory_refresh.scan_inventory') as scan:
            self.assertFalse(refresh_inventory(self.j)['enabled'])
            scan.assert_not_called()

    def test_changed_skill_set_refreshes_preserving_peer_status_and_binding(self):
        peer = self.root/'peer'/'test-check'/'SKILL.md'
        self.j.import_inventory([{'provider':'codex','id':'test-check','kind':'skill','category':'test',
                                  'status':'available','locator':str(peer)}])
        locator = tuple(self.j.db.execute('SELECT * FROM capability_locator').fetchone())
        self.prepare()
        self.skill('second-check')
        result = refresh_inventory(self.j)
        self.assertEqual(result['providers'][0]['state'], 'current')
        self.assertEqual(self.j.db.execute("SELECT count(*) FROM inventory WHERE provider='glm'").fetchone()[0], 2)
        self.assertEqual(self.j.db.execute("SELECT status FROM inventory WHERE provider='codex'").fetchone()[0], 'available')
        self.assertIn(locator, [tuple(r) for r in self.j.db.execute('SELECT * FROM capability_locator')])
        self.assertNotIn(str(self.root), json.dumps(result))
        with patch('inventory_refresh.scan_inventory') as scan:
            refresh_inventory(self.j)
            scan.assert_not_called()

    def test_failure_keeps_last_good_inventory_and_uses_backoff(self):
        self.prepare()
        before = [tuple(r) for r in self.j.db.execute('SELECT * FROM inventory')]
        (self.skills/'first-check'/'SKILL.md').unlink()
        (self.skills/'first-check').rmdir()
        self.skills.rmdir()
        result = refresh_inventory(self.j)
        self.assertEqual(result['providers'][0]['state'], 'retained-after-failure')
        self.assertEqual(before, [tuple(r) for r in self.j.db.execute('SELECT * FROM inventory')])
        with patch('inventory_refresh.scan_inventory') as scan:
            refresh_inventory(self.j)
            scan.assert_not_called()

    def test_scoped_provider_refresh_does_not_scan_peer(self):
        self.prepare()
        with patch('inventory_refresh.scan_inventory') as scan:
            self.assertEqual(refresh_inventory(self.j, ['codex'])['providers'], [])
            scan.assert_not_called()

    def test_snapshot_refreshes_only_remembered_sources_without_native_calls(self):
        from collector import snapshot
        self.prepare()
        self.skill('second-check')
        with patch('collector.adapters.load_config', return_value={'enabledProviders':['glm'],'localTokens':False,'localPatterns':False}), \
             patch('collector.collect_glm', return_value={'id':'glm','status':'unavailable','sourceStatus':['fixture']}):
            result = snapshot(self.j.state)
        self.assertTrue(result['analytics']['inventoryRefresh']['enabled'])
        self.assertEqual(result['analytics']['inventoryCount'], 2)
        self.assertNotIn('PRIVATE_', json.dumps(result))

    def test_lock_contention_fails_open_and_does_not_scan(self):
        from inventory_refresh import source_lock
        self.prepare()
        with source_lock(self.j.state), patch('inventory_refresh.scan_inventory') as scan:
            self.assertEqual(refresh_inventory(self.j)['error'], 'refresh-unavailable')
            scan.assert_not_called()

    def test_linked_profile_requires_explicit_trusted_root_and_binds_both_paths(self):
        profile = self.root/'profile'
        profile.mkdir()
        try:
            (profile/'first-check').symlink_to(self.skills/'first-check', target_is_directory=True)
        except OSError:
            self.skipTest('symlink privileges unavailable')
        self.assertEqual(scan_inventory('glm', [profile]), [])
        rows = scan_inventory('glm', [profile], trusted_skill_dirs=[self.skills])
        self.assertEqual(len(rows), 2)
        self.j.import_inventory(rows)
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM inventory').fetchone()[0], 1)
        self.assertEqual(self.j.db.execute('SELECT count(*) FROM capability_locator').fetchone()[0], 2)
        self.assertNotIn('PRIVATE_', json.dumps(rows))
        other = self.root/'other'
        other.mkdir()
        self.assertEqual(scan_inventory('glm', [profile], trusted_skill_dirs=[other]), [])

    def test_invalid_configuration_and_scan_overflow_are_explicit(self):
        config = self.root/'config.json'
        for raw in [[], {'mcp': []}, {'mcpServers': 123}, {'mcpServers': {'x'+str(n):{} for n in range(501)}}]:
            config.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                scan_inventory('glm', [self.skills], config)
        with self.assertRaises(ValueError):
            scan_inventory('glm', [self.skills]*9)

    def test_invalid_source_plan_fails_open_without_reading_outside(self):
        atomic_json(self.j.state/PLAN_FILE, {'glm': {'skills': ['/PRIVATE_OUTSIDE']}})
        with patch('inventory_refresh.scan_inventory') as scan:
            result = refresh_inventory(self.j)
            self.assertEqual(result['error'], 'invalid-sources')
            scan.assert_not_called()
        self.assertNotIn('PRIVATE_', json.dumps(result))

    def test_symlink_plan_cannot_be_replaced(self):
        destination = self.root/'outside.json'
        destination.write_text('PRIVATE_CANARY')
        try:
            (self.j.state/PLAN_FILE).symlink_to(destination)
        except OSError:
            self.skipTest('symlink privileges unavailable')
        with self.assertRaises(ValueError):
            remember_sources(self.j, 'glm', [self.skills])
        self.assertEqual(destination.read_text(), 'PRIVATE_CANARY')


if __name__ == '__main__':
    unittest.main()
