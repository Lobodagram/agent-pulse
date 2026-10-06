# Linux and headless runtime

The Python 3.11+ collector/journal and local stdio MCP are supported without a desktop widget on Linux. This is a runtime mode, not a Linux desktop installer. macOS/Windows GUI packages remain separate.

From a reviewed source checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
agent-pulse journal
agent-pulse journal --format markdown --language en
agent-pulse-mcp
```

`agent-pulse-mcp` waits for JSON-RPC on stdin; it is not a network server. Configure it explicitly in the chosen client's MCP settings. No model calls or native client launch are needed to read the local journal. An empty journal is expected until supported opt-in hooks/imports deliver actual events. Provider selection alone does not create tool tracing or expose billing data; see [provider coverage](PROVIDERS.md), [observer setup/removal](ANALYTICS.md) and [reading evidence](READING_ANALYTICS.md).

The runtime wheel includes the hook bridge and both console entry points, with no developer smoke/render scripts. Run `python scripts/package_smoke.py` from source with setuptools 68+ and wheel installed to verify an isolated build/install and fixture hook. Public source retains development tools. The metadata version comes from `pulse_version.__version__`, also used by MCP/build validation. This follows [setuptools dynamic metadata](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html#dynamic-metadata).

No Linux GUI, universal client collection or measured subscription saving is claimed. Hosted Linux tests are separate from macOS signing, Windows physical-device/DPI and native client acceptance.
