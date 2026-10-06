# Analytics readiness audit · 2026-10-06

[Русский](AUDIT.ru.md)

The product's primary goal is evidence for improving agent workspaces, not a quota meter. Readiness must include a real event path, useful findings and verified effects of subsequent changes. Current status: **public preview; not yet a complete continuous agent-work analysis system**.

## Findings corrected in 0.4.1

- The one-file frozen observer took 6–7 seconds to start on the development Mac, exceeding its configured 2-second hook deadline. Packages now use a directory runtime without per-event extraction. Packaged smoke tests enforce the actual 2-second budget, rather than a permissive 20 seconds. Native trust and new-session activation remain required.
- An explicit tool error alongside exit code zero could be reported as success. Explicit failure now takes precedence.
- Dropping failed calls before sequence analysis joined operations across failures. Failures and incomplete calls now break chains.
- A finish timestamp before its start could contribute to a sequence. Invalid timelines now break chains.
- A missing input/output token component could appear as zero. An unreported component remains unknown.
- Multiple sources for the same turn could double-count tokens. Matching values are counted once; conflicting components remain unknown.
- Lifecycle-only activity no longer has the same status as receiving tool events.
- Build guides now describe the current runtime/tray modes; the changelog is ordered and both READMEs describe analytics first.

## Verification and boundaries

83 unit tests cover pairing, retries, sequential versus parallel execution, actor isolation, incomplete/invalid calls, unknown values, inventory status, retention, privacy, inverse configuration and account history. Synthetic hook → private journal → report → local MCP verifies the event path without model calls. This does **not** establish delivery from a running native client.

For native acceptance: enable an observer, start a new session, review trust when prompted, execute a normal read/edit/test task and confirm receiving tool events, paired calls and inspectable evidence. Repeat similar tasks in at least three observed turns before expecting a workflow finding. Do not inject demonstration events into your real journal to pass this check.

Native Codex and ZCode usage counters have been verified on macOS. These counters are independent of the workflow journal. Other providers vary from explicit bridges to imports; Windows hosted tests are not physical-device/DPI acceptance. See [QA](QA.md) for dated build/package evidence and [provider coverage](PROVIDERS.md) for each adapter.

## Important gaps relative to the goal

| Goal | Current evidence | Remaining work |
| --- | --- | --- |
| Continuous event collection | Local observer mechanism and deadline tests | Native client activation/trust and real received pairs per client |
| Repeated work discovery | Deterministic category sequences, identical-input fingerprints, retries/read hints | More representative real tasks; reviewed false-positive/negative evaluation |
| Similar commands | Fixed command shapes and operation families | Compound commands collapse to a generic shape; no semantic code analysis |
| Skill/tool utilization | Sanitized tool calls and explicitly supplied inventory | Reading a skill is not proof of following it; no verified universal skill-use/non-use attribution |
| Missing MCP/skill discovery | Category-matched candidates with evidence | No match in an incomplete inventory does not prove absence; maintain reviewed live availability |
| Improvement evaluation | Manual quality/variant labels and observational comparison | Comparable tasks and verified acceptance; no causal or guaranteed token-saving claim |
| Multi-client coverage | Three opt-in native hook clients; other clients' counters/imports | Counters from a selected provider do not create a full command trace |

## Assessment

**6/10 against the primary analytics goal**, rather than the appearance of the widget. Collection readiness: 4/10; deterministic analytics: 7/10; capability attribution: 4/10; quality/effect evaluation: 5/10; privacy and bounded processing: 8/10; packaging/documentation: 8/10. These are engineering judgements, not benchmark results or a security certification. Fixing the observed defects improves reliability but does not replace native acceptance or representative data.

Priority: (1) prove the real event path, (2) collect and manually review repeated tasks, (3) add explicit skill-use evidence and inventory freshness, (4) evaluate precision of findings, (5) automate only a confirmed pattern and compare quality/work counts afterwards. A new model-driven loop, plugin catalog or vector database is not required to pass the first gate.

## Official contracts checked

[OpenAI hooks](https://learn.chatgpt.com/docs/hooks) require review of non-managed hook definitions and describe tool-coverage exceptions. [ZCode hooks](https://zcode.z.ai/en/docs/hooks) describe user configuration and session-start snapshots. The observer preserves these boundaries; it does not bypass trust or start agents.
