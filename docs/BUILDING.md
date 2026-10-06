# Building / release pipeline

Source/headless installation: in your own virtual environment run `python3 -m pip install -e .` for `agent-pulse` and `agent-pulse-mcp`. Python 3.11+ is declared in metadata. Collector startup gives a clear version message. Opt-in `--debug` prints only an exception class to stderr, never its message; hooks stay silent/fail-open. Linux supports collector/local MCP without a desktop widget; native adapters vary.

[Русский](BUILDING.ru.md)

Development requires Python 3.11+ (release CI uses 3.12). The collector has no third-party runtime Python dependency. Build-only PyInstaller is pinned in `requirements-build.txt`. Create a virtual environment for builds; do not install build dependencies globally. Native clients are optional and separately installed/authenticated.

```sh
python3 -m venv .build/venv
.build/venv/bin/python -m unittest discover -s tests -v
```

## macOS

macOS 14+, Xcode Command Line Tools. A source-only app expects Python 3.11+ as `python3` on PATH (or `AGENT_PULSE_PYTHON` set to its executable) and copies its collector modules; a redistributable release bundles a frozen collector:

```sh
.build/venv/bin/python -m pip install -r requirements-build.txt
.build/venv/bin/python -m PyInstaller --clean --noconfirm --onedir --contents-directory pulse-runtime --name pulse-collector --distpath .build collector.py
./build.sh
'dist/Agent Pulse.app/Contents/MacOS/AgentPulse' --fixture examples/demo.json --language en --snapshot .build/widget.png
open 'dist/Agent Pulse.app'
```

`build.sh` targets the current machine architecture, macOS 14+, ad-hoc signs the app, and copies the `.build/pulse-collector/` helper plus `pulse-runtime` into Resources. A release must include both. The observer must start within the native 2-second timeout; one-file extraction exceeded that budget on the development Mac. Run `python scripts/frozen_smoke.py 'dist/Agent Pulse.app/Contents/Resources/pulse-collector'` to check the packaged event path under that deadline. No Apple signing identity/notarization credentials are configured.

## Windows

Windows 10/11 x64 and official Python 3.12 with Tk. Source mode:

```powershell
python -m unittest discover -s tests -v
python windows/agent_pulse.py --fixture examples/demo.json
python windows/agent_pulse.py
```

Package in a venv, then test the **packaged** executable:

```powershell
python -m venv .build/venv
.build/venv/Scripts/python -m pip install -r requirements-build.txt
.build/venv/Scripts/python -m PyInstaller --clean --noconfirm --onedir --contents-directory pulse-runtime --console --name pulse-collector --distpath .build collector.py
New-Item -ItemType Directory -Path dist -Force | Out-Null
Copy-Item .build/pulse-collector/* dist/ -Recurse -Force
.build/venv/Scripts/python -m PyInstaller --clean --noconfirm --onefile --windowed --name AgentPulse --paths . windows/agent_pulse.py
python windows/agent_pulse.py --fixture examples/demo.json --smoke
$demo = (Resolve-Path examples/demo.json).Path
$smoke = Start-Process -FilePath dist/AgentPulse.exe -ArgumentList '--fixture',"`"$demo`"",'--smoke' -Wait -PassThru
if ($smoke.ExitCode -ne 0) { throw 'Packaged Windows smoke failed' }
```

Keep `AgentPulse.exe`, `pulse-collector.exe` and the `pulse-runtime` directory together. Run `python scripts/frozen_smoke.py dist/pulse-collector.exe` before distributing. The source and exe smoke modes use demo counters and close automatically; they do not query accounts. Windows has floating, compact-strip and native tray modes. Interactive dragging, mixed-DPI/fullscreen behavior and live Windows provider integration still need manual device acceptance.

## CI and release

`Checks` runs tests on Linux/macOS/Windows and fixture UI smoke checks on desktop runners. `Release packages` builds macOS ARM64/Intel and Windows x64, tests a frozen collector/catalog or frozen Windows demo, then uploads zip packages and SHA256SUMS to the tagged **prerelease**. Only the publish job has repository contents write permission. No user credentials or telemetry are needed in CI.

Release notes are bilingual. Package checksum files verify the downloaded bytes; they do not substitute for code signing. Tags describe preview scope; no blanket fully verified provider/OS claim is made.

Before publication, `scripts/public_export.py NEW_DIRECTORY` exports an allowlisted tree, excludes private Git history/local state and scans text for personal home paths/credential patterns. Use only `examples/demo.json` to render public screenshots. Private project context/QA are not part of that export.

Local Mac development: `script/build_and_run.sh` builds/launches an isolated local-run bundle; `--verify`, `--debug`, `--logs`, `--telemetry` supported. Set `AGENT_PULSE_PYTHON` to a Python 3.11+ interpreter for source builds without the frozen collector. Fixture/snapshot paths are resolved from the repository. Public release bundles still use `build.sh` and bundled Python.
