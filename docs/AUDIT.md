# Analytics readiness audit · 2026-10-06

## 0.5.2 update

**7/10 against the primary analytics goal**: collection 6, bounded mechanics 8, capability attribution 6, effect evaluation 5, privacy 8, delivery 8. Engineering judgements, not certification. Representative reviewed real repeated tasks, completed ZCode shell outcomes and physical Windows acceptance remain missing. Synthetic precision is not production accuracy.

115 tests and 14 invented labeled mechanics cases cover operation distinctions, strict outcomes, parallel/nested barriers, registered capability evidence, provider isolation, retention and review packs. [OpenAI native payload code](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/context.rs) can deliver stdout-only shell hook responses; those deliberately remain unknown. See [current evidence contracts](EVIDENCE.md).

Source/tag 0.5.2 and three platform packages are verified in [QA](QA.md). Physical Intel chart rendering remains unverified; hosted focus checks use text-only Workflows.

The 0.4.1 sections below are historical. Generic compound grouping and absent capability attribution are superseded by bounded families and registered evidence. Semantic code interpretation and universal non-use proof remain unavailable.

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

Explicitly authorized native read/status acceptance on the development Mac subsequently established receiving and paired calls from Codex CLI 0.160.0 after its standard hook review. Shell outcomes remained `unknown`, with measured hook-wall durations; paired events alone do not establish an exit status. ZCode desktop 3.14.4 delivered a successful Read pair and the start of Bash, then displayed an overload error. Bash remained pending, so complete ZCode task/outcome coverage has not passed. The bundled ZCode CLI 0.16.9 independently failed during model creation before hooks. No raw hook payloads were retained or published; native conversation stores were not read; no model/account/subscription setting was changed. These were human-authorized acceptance tasks, not an Agent Pulse agent loop.

Native Codex and ZCode usage counters have been verified on macOS. These counters are independent of the workflow journal. Other providers vary from explicit bridges to imports; Windows hosted tests are not physical-device/DPI acceptance. See [QA](QA.md) for dated build/package evidence and [provider coverage](PROVIDERS.md) for each adapter.

## Important gaps relative to the goal

| Goal | Current evidence | Remaining work |
| --- | --- | --- |
| Continuous event collection | Deadline tests, real Codex pairs and ZCode desktop Read pair | Completed ZCode task, correct native shell outcomes, sustained and per-client coverage |
| Repeated work discovery | Deterministic category sequences, identical-input fingerprints, retries/read hints | More representative real tasks; reviewed false-positive/negative evaluation |
| Similar commands | Fixed command shapes and operation families | Compound commands collapse to a generic shape; no semantic code analysis |
| Skill/tool utilization | Sanitized tool calls and explicitly supplied inventory | Reading a skill is not proof of following it; no verified universal skill-use/non-use attribution |
| Missing MCP/skill discovery | Category-matched candidates with evidence | No match in an incomplete inventory does not prove absence; maintain reviewed live availability |
| Improvement evaluation | Manual quality/variant labels and observational comparison | Comparable tasks and verified acceptance; no causal or guaranteed token-saving claim |
| Multi-client coverage | Three opt-in native hook clients; other clients' counters/imports | Counters from a selected provider do not create a full command trace |

## Assessment

**6/10 against the primary analytics goal**, rather than the appearance of the widget. Collection readiness: 6/10 after bounded native acceptance; deterministic analytics: 7/10; capability attribution: 4/10; quality/effect evaluation: 5/10; privacy and bounded processing: 8/10; packaging/documentation: 8/10. These are engineering judgements, not benchmark results or a security certification. Real event receipt improves collection evidence, but the remaining unknown/pending outcomes and absence of representative repeated tasks prevent a higher overall readiness claim.

Priority: (1) prove the real event path, (2) collect and manually review repeated tasks, (3) add explicit skill-use evidence and inventory freshness, (4) evaluate precision of findings, (5) automate only a confirmed pattern and compare quality/work counts afterwards. A new model-driven loop, plugin catalog or vector database is not required to pass the first gate.

## Official contracts checked

[OpenAI hooks](https://learn.chatgpt.com/docs/hooks) require review of non-managed hook definitions and describe tool-coverage exceptions. [ZCode hooks](https://zcode.z.ai/en/docs/hooks) describe user configuration and session-start snapshots. The observer preserves these boundaries; it does not bypass trust or start agents.
