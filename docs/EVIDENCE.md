[0.7.0 literal-reader sources, namespaces and reviewed rechecks](IMPROVEMENT_LOOP.md). Reading may be partial/empty and is not proof of application.

# Evidence contracts in 0.5.0

[Русский](EVIDENCE.ru.md)

## Outcome clarification in 0.9.6

Malformed non-null exit metadata in a recognized code-mode result makes the result unknown, even if another location reports zero. A shell result with more than ten content blocks or an inspected text block over 128 KiB reports `result-limit-exceeded`; skipped data cannot support success. These are limits on evidence, not command failures. Explicit native failure/error flags still take priority. No stdout regex, output retention, command rewrite or new execution wrapper is introduced. Previously stored events cannot be reclassified because raw results are deliberately not retained.

Checked 2026-10-07: [Codex hooks](https://developers.openai.com/codex/hooks/#posttooluse) run for shell calls with nonzero exits too; event completion alone is not success. The [0.160.0 native result implementation](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/core/src/tools/context.rs) sends truncated text on the inspected shell hook path and has a separate structured code-mode result. They are different delivery paths: Agent Pulse cannot recover missing native shell exits from ordinary hook stdout. GLM structured exits remain supported; no client session is started to acquire new evidence.

Capabilities distinguishes `loaded` (successful Read of an exactly registered HMAC skill-file locator), `invoked` (successful explicit Skill/tool or registered MCP-prefix call), and `declared` (manual session assertion). Reading instructions does not prove following them; no observed use never proves non-use. Only reviewed inventory IDs are retained. Optional inventory `locator` is an absolute skill-file path, immediately hashed and never stored literally. Scanning names does not read instructions. Failed/unknown calls do not establish successful capability use.

Manual declaration: `python3 collector.py journal --action declare --provider codex --session HASH --capability REVIEWED_ID --kind skill`. Session and inventory entry must already exist. This is labeled separately from native invocation.

Result provenance distinguishes native failure, structured exit metadata, completed non-shell operations, missing exit metadata and running processes. Raw stdout, including text saying `Exit code: 0`, cannot establish shell success. Conflicting known finishes become unknown and revoke automatic capability evidence; a later valid exit can clarify an unknown finish. Missing finishes after session boundaries are collection gaps, not failures. Pending calls without boundaries become stale after ten minutes.

Known compound shell commands retain bounded sanitized operation families and operators. Substitutions, unsupported syntax and unknown executables stay unclassified. No commands execute during analysis; static parsing is not proof that every branch ran. Sequences use families as well as categories and break across overlaps, failures, running processes, invalid timelines and missing finishes. Generic unknown executables do not create automation suggestions.

Cross-client candidates require a shared known project fingerprint, the same operation family, two providers, three turns and six calls. They remain low confidence: a shared family does not prove task equivalence.

Review pack: `python3 collector.py journal --action evidence --finding FINDING_ID --file /private/evidence.json`. Optional read-only MCP `pulse_evidence` provides the same bounded current-journal evidence. Review coverage, task equivalence, existing capabilities and acceptance before proposing a script/skill/MCP. The pack neither installs skills nor executes commands. Exact per-tool billing and guaranteed savings are unavailable.

`python3 scripts/analytics_benchmark.py` evaluates 14 invented labeled mechanics cases in temporary journals, without models or production data. Five expected positive finding kinds, zero false positives and zero missed expected kinds apply only to this small suite; they are not real-task semantic accuracy or savings.
