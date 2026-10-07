"""Real independent writers, read-only inspection and lock failure boundaries."""
import json
from contextlib import closing
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import agent_control
import providers

def held_writer(directory,entered,release):
    original=providers.atomic_json
    def delayed(path,value):
        entered.set()
        if not release.wait(5):raise TimeoutError('test_release')
        original(path,value)
    with patch('providers.atomic_json',side_effect=delayed):
        agent_control.update_settings(directory,{'language':'ru'})

def parallel_writer(directory,start,field,value):
    if not start.wait(5):raise TimeoutError('test_start')
    for _ in range(12):agent_control.update_settings(directory,{field:value})

class SettingsConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.state=Path(self.tmp.name)/'state'
    def tearDown(self):self.tmp.cleanup()
    def test_read_absent_state_creates_nothing(self):
        self.assertEqual(agent_control.settings(self.state)['subscriptions'],{})
        self.assertFalse(self.state.exists())
    def test_read_existing_legacy_database_does_not_migrate_or_change_bytes(self):
        self.state.mkdir();path=self.state/'metrics.sqlite'
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT)')
            db.executemany('INSERT INTO settings VALUES (?,?)',[
                ('glm',json.dumps({'date':'2026-11-01','kind':'renewal','source':'manual'})),
                ('_projection_version','"1"'),('_account_codex','"private-canary"')])
            db.commit()
        before=path.read_bytes();files=set(self.state.iterdir())
        result=agent_control.settings(self.state)
        self.assertEqual(set(result['subscriptions']),{'glm'})
        self.assertNotIn('private-canary',json.dumps(result))
        self.assertEqual(path.read_bytes(),before);self.assertEqual(set(self.state.iterdir()),files)
    def test_read_database_without_settings_table_does_not_create_it(self):
        self.state.mkdir();path=self.state/'metrics.sqlite'
        with closing(sqlite3.connect(path)) as db:db.execute('CREATE TABLE existing(x)');db.commit()
        before=path.read_bytes()
        self.assertEqual(agent_control.settings(self.state)['subscriptions'],{})
        self.assertEqual(before,path.read_bytes())
    def test_contended_patches_merge_and_revisions_count_every_write(self):
        ctx=multiprocessing.get_context('spawn');start=ctx.Event()
        workers=[ctx.Process(target=parallel_writer,args=(str(self.state),start,k,v))
                 for k,v in [('language','ru'),('metricMode','today'),('topmost',False)]]
        try:
            for p in workers:p.start()
            start.set()
            for p in workers:p.join(15);self.assertEqual(p.exitcode,0)
        finally:
            for p in workers:
                if p.is_alive():p.terminate();p.join()
        config=providers.load_config(self.state)
        self.assertEqual(config['configRevision'],36)
        self.assertEqual((config['language'],config['metricMode'],config['topmost']),('ru','today',False))
    def test_lock_timeout_keeps_previous_config_and_recovers_after_release(self):
        agent_control.update_settings(self.state,{'metricMode':'limits'})
        before=(self.state/'config.json').read_bytes()
        ctx=multiprocessing.get_context('spawn');entered=ctx.Event();release=ctx.Event()
        worker=ctx.Process(target=held_writer,args=(str(self.state),entered,release));worker.start()
        try:
            self.assertTrue(entered.wait(5));started=time.monotonic()
            with self.assertRaises(TimeoutError):agent_control.update_settings(self.state,{'topmost':False})
            self.assertLess(time.monotonic()-started,2)
            self.assertEqual((self.state/'config.json').read_bytes(),before)
        finally:
            release.set();worker.join(10)
            if worker.is_alive():worker.terminate();worker.join()
        self.assertEqual(worker.exitcode,0)
        agent_control.update_settings(self.state,{'metricMode':'today'})
        config=providers.load_config(self.state)
        self.assertEqual(config['language'],'ru');self.assertEqual(config['metricMode'],'today')
        self.assertEqual(config['configRevision'],3)
    @unittest.skipIf(os.name=='nt','symlink privilege differs on Windows')
    def test_symlink_state_database_and_lock_are_refused(self):
        self.state.mkdir();other=Path(self.tmp.name)/'other';other.mkdir()
        (self.state/'metrics.sqlite').symlink_to(other/'db')
        with self.assertRaises(ValueError):agent_control.settings(self.state)
        (self.state/'metrics.sqlite').unlink()
        (self.state/'.config.lock').symlink_to(other/'lock')
        with self.assertRaises(ValueError):agent_control.update_settings(self.state,{'language':'ru'})
        self.assertFalse((other/'lock').exists())

if __name__=='__main__':unittest.main()
