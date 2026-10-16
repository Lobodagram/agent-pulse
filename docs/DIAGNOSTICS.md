# Failure diagnostics and inventory freshness

Prepared 0.14.6 adds `resultEvidence` per provider over the whole selected call population: missing finishes, completed unknown results, terminal evidence sources and unknown-result tools. Newly received terminal events retain `responseEnvelope` in a separate `response_envelope` table: fixed JSON container types, exit-field states, bounded content/wrapper counts and the existing reported failure-category source. No raw keys, command output, messages or stack traces survive. This is diagnostic evidence, not another outcome classifier. Stringified JSON/plain stdout, unsupported fields and missing native exits remain unknown.

The envelope is from the first received terminal event; a later retry may update the existing native outcome without changing that original shape. Old rows/retries are not backfilled. Corrupt/absent envelope evidence remains unavailable. `envelopeRecorded` counts finished events with usable shape evidence, not known outcomes or paired results. Pending events never have a finish envelope. Unknown-result shape counts include received terminal phases even when a start is missing. Existing `call_metadata` retains its three-column contract and all previous outcome rules remain unchanged.

Codex's [official PostToolUse contract](https://learn.chatgpt.com/docs/hooks), checked 2026-10-16, exposes tool-specific JSON output and normally model-facing output for local tools; it does not promise a typed exit field for every tool. Do not parse strings pretending to be exit codes or infer an error-free day from missing results. The daily result evidence helps distinguish hook delivery gaps from absent recognizable exit metadata. Historical native envelopes were not retained and cannot be reconstructed.

[Русский](DIAGNOSTICS.ru.md)

`commandCoverage` counts recorded shell-tool calls whose outer invocation has a recognized operation family, including pending/failed calls. This is independent of outcome coverage. Version 0.14.2 projects bounded newlines, simple redirects, common checks/file commands, directory/environment prefixes and a single terminal here-document. A Python/Node/shell body remains opaque: `run.python-stdin` means the outer invocation, not tests, deployment or successful execution. Dynamic substitutions, malformed redirects, nonterminal/multiple here-documents and unsupported syntax remain unknown. Arguments, paths, code and delimiter names are discarded. Retained old unknown commands cannot be reclassified; bodies were never saved.

`skillEvidenceCoverage` separates successful native Skill calls matched to a reviewed catalog, successful unmatched Skill calls and exact skill-file reads. Unknown names are counted without retaining them. The catalog includes identities and hashed locations already scanned for supported clients; a successful GLM read of an exact shared catalog file can be recorded under GLM even when that skill is absent from GLM's profile inventory. An unrelated file with the same basename cannot match. Cross-client MCP configuration is never reused to assert invocation/availability. Such skill evidence remains `not-in-current-inventory` for the actual client; scans do not become availability or use. Only future native events add this evidence. Historical paths or missing Skill events cannot be reconstructed.

A file read proves observed access only. A successful native Skill event proves reported name invocation, not the skill's version, application to a task or quality. Existing version registration and explicit task assessments in [the improvement loop](IMPROVEMENT_LOOP.md) are still needed for adoption and before/after comparisons. With no events, non-use is unknown. No new agent loop or automatic task/acceptance annotation is enabled.

Pulse diagnostics aggregate retained sanitized metadata by client, tool and operation family. A family with at least three failed paired calls is flagged for review even when the inputs differ. The flag is separate from an identical-input retry finding: neither establishes a shared cause or a missing skill. Historical error messages are not retained and cannot be reconstructed.

Future failed native events can retain a fixed reported category such as syntax, reference, type, timeout, permission or module-not-found. Only allowlisted structured error names/codes or a fixed exception header at the beginning of a bounded non-shell failed response are considered. Messages, arguments and stacks are discarded. Conflicting labels remain conflicting; absent labels remain unknown. These are client-reported categories, not verified causes. Shell output and successful tool output never supply exception-header categories. A separate side table preserves the old collectors' metadata insert schema.

`observedFailureRate` divides failed paired calls by paired calls with a known native success/failure. Unknown exits, pending calls and missing starts stay outside that denominator; `outcomeCoverage` shows the known fraction of all selected calls. Zero known results yields an unavailable rate. A completed MCP call only has the existing native envelope semantics; diagnostics do not verify the returned business result. Tool-group/failure-group caps are marked explicitly.

```sh
python collector.py journal --action diagnostics
python collector.py journal --action diagnostics --date 2026-10-10 --utc-offset-minutes 120
```

The local-day selection uses call start time, or finish time for a missing start, from the full retained selection. It does not use the last 100-call preview. Provide the offset applicable to that date; default is UTC. Retention and unknown observer coverage still apply. The read-only MCP `pulse_diagnostics` accepts optional `date` and `utcOffsetMinutes`. The ordinary report and bilingual review pack also include diagnostics.

Inventory scan dates describe discovery, not live availability or use. Entries younger than seven days are current under the existing freshness policy, even if a new skill was added after the scan. Rescan explicit folders/configuration when the environment changes:

```sh
python collector.py journal --action scan --provider codex --skills-dir /absolute/skills
python collector.py journal --action scan --provider glm --skills-dir /absolute/profile --trusted-skills-dir /absolute/shared-skills
```

Folder links are skipped by default. `--trusted-skills-dir` permits only links whose resolved target is a direct skill folder in that explicitly trusted directory. SKILL.md file links are still skipped. Instructions are never read during scans. Accepted linked skills bind both profile and resolved path hashes, so either native read path can be recognized. No proof of comprehension/application follows from a file read.

Add `--remember-sources` to a successful scan to opt in to hourly rescans during ordinary snapshots. Only those explicit sources are visited; no implicit client, plugin-cache, project or session discovery occurs. Local `inventory-sources.json` stores source paths and scan times, without credentials. Paths never enter diagnostics, telemetry exports or MCP responses. Scan data contains only capability identities/statuses and hashed skill locations. Newly scanned capabilities remain configured, not live-verified.

An unavailable/invalid source preserves the last good provider inventory and retries after one hour. Peers' statuses and hashed bindings are preserved. Source writes are serialized with a bounded lock. Oversized scans fail explicitly rather than replacing a registry with a partial prefix. This is an inventory refresh, not a tool invocation, model call or second agent loop. To disable remembered rescans, remove the local `inventory-sources.json`; no native client settings are changed.

Failure diagnosis does not claim token savings. Explicit helper receipts remain separate from native outcomes and human task acceptance. Plain shell output is never parsed as a trustworthy exit code.

## Recognition reasons and collector provenance

Prepared 0.14.5 retains bounded component labels for newly received shell events in a separate `command_components` table. A partly known chain keeps its whole-call operation unknown; diagnostics separately show the known families inside it. Component labels do not establish which branch ran, per-component success or task purpose. A pipe or conditional operator is only recorded syntax. Opaque bodies and unknown invocations remain opaque. Standalone literal shell assignments and outer `echo`/`printf` invocations now have fixed families; quoted command names resembling assignments remain unknown. Calls containing only assignments/output are excluded from automation hypotheses and remain barriers in sequences, while their calls/outcomes remain counted. No historical event or duplicate delivery is backfilled.

`commandCoverage.components` reports evidence coverage, parsed states, partial-call counts and known/unknown component counts. Components are not extra tool calls. Legacy or malformed stored evidence is unavailable, rather than an all-zero whole-population result. Individual calls expose `commandComponents` for the preferred start phase (finish for missing starts); absent start metadata is not borrowed from a newer finish. Templates, counters and execution outcomes from previous versions are preserved. `call_metadata` retains its original three-column schema for older observers.

From 0.14.4, future received tool events include a public collector version and a fixed recognition reason in a separate `collection_metadata` table. The old three-column `call_metadata` write contract is preserved. Reasons distinguish missing/oversized commands, unsupported terminal here-docs, shell substitution, line/chain limits, unsupported redirects, incomplete quoting, unrecognized invocations and partially known chains. They explain a parser limitation, not command purpose, a missing executable or an error cause. Recognition rules remain conservative.

The parser emits only fixed labels; command text, script bodies, destinations and exception messages are not stored. A supported terminal here-doc's body is discarded before checking substitutions, so opaque body text never supplies the reason. Historical records and duplicate deliveries are not backfilled. Old reasons show `not-recorded`, not a guessed explanation.

Calls expose `collectorVersion`, `collectorVersions` and `collectorVersionCoverage`. This is the version that first processed each received event, not the native client/tool/model version or exact execution-time version. Coverage describes observed phases; it does not establish a complete start/finish pair. Missing phase metadata stays partial/unknown; different recorded versions stay mixed. Diagnostics, local-day JSON and Markdown report counts by collector version. Projected historical events, if enabled, describe projection-time collector provenance.

These fields support prospective coverage comparisons. They do not prove task equivalence, quality, skill application or subscription savings. Nonzero shell exits remain technical unsuccessful outcomes; their cause and whether the task required such a result remain unverified.
