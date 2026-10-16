"""Opt-in bounded rescans of explicit inventory roots; no client discovery."""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from journal import PROVIDERS, atomic_json
from instrumentation import scan_inventory

PLAN_FILE = 'inventory-sources.json'
REFRESH_SECONDS = 3600


@contextmanager
def source_lock(state):
    path = Path(state) / '.inventory-sources.lock'
    if path.is_symlink():
        raise ValueError('symlink_inventory_lock')
    with os.fdopen(os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600), 'r+b') as lock:
        if os.name == 'nt':
            import msvcrt
        else:
            import fcntl
            os.fchmod(lock.fileno(), 0o600)
        deadline = time.monotonic() + .5
        while True:
            try:
                if os.name == 'nt':
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('inventory_busy') from None
                time.sleep(.01)
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def load_plans(state):
    path = Path(state) / PLAN_FILE
    if path.is_symlink():
        raise ValueError('symlink_inventory_sources')
    if not path.exists():
        return {}
    if path.stat().st_size > 65536:
        raise ValueError('invalid_inventory_sources')
    plans = json.loads(path.read_text())
    if not isinstance(plans, dict) or set(plans) - PROVIDERS:
        raise ValueError('invalid_inventory_sources')
    for spec in plans.values():
        if not isinstance(spec, dict) or set(spec) != {'skills', 'trustedSkills', 'config', 'lastAttempt', 'lastSuccess', 'error'}:
            raise ValueError('invalid_inventory_sources')
        for key in ('skills', 'trustedSkills'):
            if not isinstance(spec[key], list) or len(spec[key]) > 8:
                raise ValueError('invalid_inventory_sources')
            for path in spec[key]:
                if not isinstance(path, str) or len(path) > 4096 or not Path(path).is_absolute():
                    raise ValueError('invalid_inventory_sources')
        config = spec['config']
        if config is not None and (not isinstance(config, str) or len(config) > 4096 or not Path(config).is_absolute()):
            raise ValueError('invalid_inventory_sources')
        for key in ('lastAttempt', 'lastSuccess'):
            if type(spec[key]) not in (float, int) or not 0 <= spec[key] <= 10**12:
                raise ValueError('invalid_inventory_sources')
        if spec['error'] not in (None, 'scan-failed'):
            raise ValueError('invalid_inventory_sources')
    return plans


def remember_sources(j, provider, skills, config=None, trusted_skills=()):
    with source_lock(j.state):
        _remember_sources(j, provider, skills, config, trusted_skills)


def _remember_sources(j, provider, skills, config=None, trusted_skills=()):
    plans = load_plans(j.state)
    plans[provider] = {'skills': [str(Path(p).absolute()) for p in skills],
                       'trustedSkills': [str(Path(p).absolute()) for p in trusted_skills],
                       'config': str(Path(config).absolute()) if config else None,
                       'lastAttempt': time.time(), 'lastSuccess': time.time(), 'error': None}
    # Validate the same schema before committing any local source configuration.
    if provider not in PROVIDERS or len(skills) > 8 or len(trusted_skills) > 8 or not (skills or config):
        raise ValueError('invalid_inventory_sources')
    atomic_json(j.state / PLAN_FILE, plans)


def replace_provider(j, provider, rows):
    with j.db:
        j.db.execute('BEGIN IMMEDIATE')
        peers = [dict(r) for r in j.db.execute('SELECT * FROM inventory WHERE provider!=?', (provider,))]
        j.import_inventory(peers + rows)


def refresh_inventory(j, providers=None):
    # No opt-in file means no scan and no new configuration/lock file.
    if not (j.state / PLAN_FILE).exists() and not (j.state / PLAN_FILE).is_symlink():
        return {'enabled': False, 'intervalSeconds': REFRESH_SECONDS, 'providers': []}
    try:
        with source_lock(j.state):
            return _refresh_inventory(j, providers)
    except (ValueError, OSError):
        return {'enabled': True, 'error': 'refresh-unavailable', 'providers': []}


def _refresh_inventory(j, providers=None):
    try:
        plans = load_plans(j.state)
    except (ValueError, OSError):
        return {'enabled': False, 'error': 'invalid-sources', 'providers': []}
    now = time.time()
    changed = False
    statuses = []
    for provider, spec in plans.items():
        if providers is not None and provider not in providers:
            continue
        if now < spec['lastAttempt'] or now - spec['lastAttempt'] >= REFRESH_SECONDS:
            changed = True
            spec['lastAttempt'] = now
            try:
                rows = scan_inventory(provider, spec['skills'], spec['config'], spec['trustedSkills'])
                replace_provider(j, provider, rows)
                spec['lastSuccess'] = now
                spec['error'] = None
            except (ValueError, OSError, sqlite3.Error):
                spec['error'] = 'scan-failed'
        statuses.append({'provider': provider, 'lastSuccess': spec['lastSuccess'],
                         'error': spec['error'], 'state': 'retained-after-failure' if spec['error'] else 'current'})
    if changed:
        try:
            atomic_json(j.state / PLAN_FILE, plans)
        except (ValueError, OSError):
            return {'enabled': True, 'error': 'save-failed', 'providers': statuses}
    return {'enabled': bool(plans), 'intervalSeconds': REFRESH_SECONDS, 'providers': statuses}
