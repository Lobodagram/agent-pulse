#!/usr/bin/env python3
"""Consolidate existing own-window fixture suites; cache exact verified artifacts only."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SUITES = {'widget': 'widget_smoke.py', 'models': 'model_ui_smoke.py',
          'charts': 'chart_ui_smoke.py', 'efficiency': 'efficiency_ui_smoke.py'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree_digest(root):
    root = Path(root).resolve()
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise ValueError('external_bundle_symlink')
            body = ('link:' + os.readlink(path)).encode()
        elif path.is_file():
            body = bytes.fromhex(sha(path))
        else:
            continue
        digest.update(path.relative_to(root).as_posix().encode() + b'\0' + body)
    return digest.hexdigest()


def input_identity(binary):
    binary = Path(binary).resolve(strict=True)
    bundle = binary.parents[2]
    if (binary.name != 'AgentPulse' or binary.parent.name != 'MacOS' or
            binary.parent.parent.name != 'Contents' or bundle.suffix != '.app'):
        raise ValueError('expected_own_app_binary')
    import plistlib
    info = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
    if not str(info.get('CFBundleIdentifier', '')).startswith('app.agentpulse.'):
        raise ValueError('not_agent_pulse_bundle')
    # Hash every bundle byte, demo input and suite implementation. Never hash live state.
    return {'bundleSha256': tree_digest(bundle), 'fixtureSha256': sha(ROOT / 'examples/demo.json'),
            'runnerSha256': sha(__file__), 'python': sys.version, 'pythonExecutable': sys.executable,
            'platform': platform.platform(), 'machine': platform.machine(),
            'suiteScripts': {name: sha(ROOT / 'scripts' / script) for name, script in SUITES.items()}}


def artifacts(directory):
    rows = []
    for path in sorted(Path(directory).rglob('*.png')):
        receipt = path.with_suffix('.png.json')
        if path.is_symlink() or receipt.is_symlink() or not receipt.is_file():
            raise ValueError('missing_or_symlink_fixture_receipt')
        data = json.loads(receipt.read_text())
        if data.get('fixtureMode') is not True or path.stat().st_size <= 100:
            raise ValueError('not_fixture_artifact')
        rows.append({'path': path.relative_to(directory).as_posix(), 'sha256': sha(path),
                     'receiptPath': receipt.relative_to(directory).as_posix(), 'receiptSha256': sha(receipt)})
    if not rows:
        raise ValueError('no_fixture_artifacts')
    return rows


def reuse(previous, name, identity, previous_root):
    """A caller supplies a trusted local receipt; hashes still verify every retained byte."""
    if not isinstance(previous, dict) or previous.get('schemaVersion') != 1:
        return None
    old = previous.get('inputs', {})
    # Other suite changes do not invalidate this suite's cache.
    keys = ['bundleSha256', 'fixtureSha256', 'runnerSha256', 'python', 'pythonExecutable', 'platform', 'machine']
    if any(old.get(k) != identity[k] for k in keys) or old.get('suiteScripts', {}).get(name) != identity['suiteScripts'][name]:
        return None
    row = next((r for r in previous.get('suites', []) if r.get('name') == name), None)
    if not row or row.get('status') != 'passed' or not row.get('artifacts'):
        return None
    try:
        for item in row['artifacts']:
            for key, hkey in [('path', 'sha256'), ('receiptPath', 'receiptSha256')]:
                rel = Path(item[key])
                if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0] != name:
                    return None
                path = Path(previous_root) / rel
                if path.is_symlink() or not path.resolve().is_relative_to(Path(previous_root).resolve()) or sha(path) != item[hkey]:
                    return None
            if json.loads((Path(previous_root) / item['receiptPath']).read_text()).get('fixtureMode') is not True:
                return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return row


def gallery(output, suites):
    cards = []
    for suite in suites:
        for item in suite.get('artifacts', []):
            name = html.escape(item['path'])
            cards.append(f'<figure><a href="{name}"><img loading="lazy" src="{name}" alt="{name}"></a><figcaption>{name}</figcaption></figure>')
    text = '<!doctype html><meta charset="utf-8"><title>Agent Pulse fixture review</title>'
    text += '<style>body{font:16px system-ui;margin:24px;background:#eef0f3;color:#18202c}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}figure{margin:0;background:white;padding:16px}img{max-width:100%;height:auto}figcaption{margin-top:12px;overflow-wrap:anywhere}</style>'
    text += '<h1>Agent Pulse fixture review</h1><p>Synthetic counters only. Automated assertions and visual inspection are separate. Click a screenshot for full resolution.</p><main>' + ''.join(cards) + '</main>'
    (Path(output) / 'gallery.html').write_text(text)


def run(binary, output, suites=None, previous=None, runner=subprocess.run):
    if sys.platform != 'darwin':
        raise ValueError('macos_fixture_suites_only')
    names = list(SUITES) if suites is None else suites
    if not names or len(set(names)) != len(names) or any(n not in SUITES for n in names):
        raise ValueError('invalid_suite_selection')
    output = Path(output).absolute()
    # A fresh directory prevents leftover pictures from appearing as new passed checks.
    if output.exists() or output.is_symlink() or output.parent.is_symlink():
        raise ValueError('fresh_output_directory_required')
    identity = input_identity(binary)
    old = None
    previous_root = None
    if previous:
        previous = Path(previous)
        if previous.is_symlink() or previous.stat().st_size > 1024 * 1024:
            raise ValueError('invalid_previous_receipt')
        old = json.loads(previous.read_text())
        previous_root = previous.parent
    output.mkdir(parents=True, mode=0o700)
    results = []
    for name in names:
        target = output / name
        target.mkdir()
        started = time.monotonic()
        cached = reuse(old, name, identity, previous_root) if old else None
        row = {'name': name, 'status': 'failed', 'reused': False, 'artifacts': []}
        try:
            if cached:
                for item in cached['artifacts']:
                    for key in ['path', 'receiptPath']:
                        dst = output / item[key]
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(previous_root / item[key], dst)
                row.update(status='passed', reused=True, artifacts=cached['artifacts'])
            else:
                result = runner([sys.executable, str(ROOT / 'scripts' / SUITES[name]), str(Path(binary).resolve()), str(target)],
                                cwd=ROOT, capture_output=True, text=True, timeout=360, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
                (output / (name + '.log')).write_text(result.stdout + result.stderr)
                row['exitCode'] = result.returncode
                if result.returncode == 0:
                    found = artifacts(target)
                    row.update(status='passed', artifacts=[{**item, 'path': name + '/' + item['path'],
                                                           'receiptPath': name + '/' + item['receiptPath']} for item in found])
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            row['failureClass'] = type(error).__name__
        row['elapsedSeconds'] = time.monotonic() - started
        results.append(row)
        # Persist progress before the next suite. Never cache a failed/partial suite.
        receipt = {'schemaVersion': 1, 'inputs': identity, 'suites': results, 'status': 'running',
                   'syntheticOnly': True, 'modelsCalled': 0, 'liveStateWritten': False,
                   'visualInspectionRequired': True}
        (output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
        print(json.dumps({'suite': name, 'status': row['status'], 'reused': row['reused'], 'renders': len(row['artifacts'])}), flush=True)
    unchanged = input_identity(binary) == identity
    receipt.update(status='passed' if unchanged and all(r['status'] == 'passed' for r in results) else 'failed', inputStable=unchanged)
    if not unchanged:
        for row in results:
            row['status'] = 'invalidated'
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    gallery(output, results)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suites', nargs='+', choices=sorted(SUITES))
    parser.add_argument('--previous', type=Path, help='Trusted local receipt; bundle, environment, suite and artifact hashes must match')
    args = parser.parse_args()
    receipt = run(args.binary, args.output, args.suites, args.previous)
    print(json.dumps({'status': receipt['status'], 'receipt': str(args.output / 'receipt.json'),
                      'gallery': str(args.output / 'gallery.html'), 'visualInspectionRequired': True}))
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
