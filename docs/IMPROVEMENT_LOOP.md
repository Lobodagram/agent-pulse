# Review → implement → observe

## Task eligibility and version lifecycle (0.12.0 source candidate)

In Workflows, confirm a repeat or dismiss it with a reason: waiting for a process,
required check, different task, false positive, duplicate or not applicable.
Dismissed candidates are hidden by default but remain available via the toggle,
review list, Markdown and MCP. Reasons are human annotations; they do not train a
model or prove semantic precision on unreviewed work.

Register the immutable asset version with the finding ID. In Sessions, select one
contiguous actual task and the asset version. Assess `eligibility: yes|no|unknown`,
attest application if it occurred, and review acceptance separately. For an
unapplied version, record `nonUseReason`: `unknown`, `unavailable`, `not-selected`,
`workflow-mismatch` or `preferred-alternative`. An empty reason leaves application
unassessed. A non-empty reason explicitly attests non-use. Contradictory use claims
are rejected atomically; omitted fields preserve an existing assessment.

Adoption = declared uses / explicitly eligible selected tasks, only if application
is known for every task in that denominator. The card also shows eligibility and
application coverage. This is a reviewed sample, not all opportunities in a
client. Old journals migrate with unknown eligibility; no historical backfill.
Task assessments expire with the existing 30-day task retention.

Stages are reviewed, implemented without linked version, version awaiting use,
used awaiting acceptance, accepted awaiting comparison, or dismissed. They are
evidence stages, not causal effectiveness claims. The card retains failed/rework
attempts and independent usage/time coverage. Compare equivalent accepted tasks
in Compare before judging improvement; a cache ratio is not subscription savings.
CLI metadata and opt-in MCP `pulse_record_task` use the same optional fields;
default MCP remains read-only. Synthetic fixtures never populate live reviews.

Agent Pulse 0.7.0 records manual finding decisions (`open`, `actioned`, `dismissed`) in its own local journal. Mark an implemented script/skill/MCP in Workflows or use:

```sh
python collector.py journal --action review --finding <finding-id> --status actioned --reason skill --days 1
python collector.py journal --format markdown --language en
python collector.py journal --action export --format markdown --language en --file review.md
```

Review uses equal 1/3/7-day windows for the same provider and hashed project. The default UI window is 24 hours. A recheck waits until that window ends; with fewer than three known turns in either window it reports insufficient evidence. If a finding stops meeting the discovery threshold, occurrences remain unknown, not zero or resolved. Equal windows do not establish equal tasks, difficulty, models or causation. No token/subscription saving is computed. At most 30 reviews are reported, 200 stored, with 30-day retention. Reopening/dismissing a stored decision works even if its finding disappears (CLI). Kind-scoped finding identifiers changed in 0.7.0; reselect from a fresh report instead of reusing earlier exported IDs.

The optional read-only local MCP now includes `pulse_review_pack` with `language: en|ru`. It returns a bounded human Markdown summary; it cannot mark decisions, execute code, edit clients or launch agents. Raw arguments/results/messages remain excluded. Export stays on the device; share only after review.

## Source delivery helper

```sh
python scripts/workflow_check.py check --output work/check.json
python scripts/workflow_check.py handoff --input work/check.json --output work/handoff.json
# Optional downloaded release archives plus SHA256SUMS.txt:
python scripts/workflow_check.py check --archives work/downloads --output work/check.json
```

One source check combines allowlisted privacy export, Python syntax, local document links and unit tests. The pack carries source commit, dirty status and public source-tree digest, not commands/output/credentials. Handoff validates scalar metadata and drops unrecognized fields. Archive checks verify hashes, traversal, runtime/notices and Mac bundle version; they do not execute binaries or claim Windows version verification. Native UI, hook deadlines, signatures, CI and installed acceptance remain separate release gates. Reuse an existing pack only when its exact source tree and applicable checks still match; rerun after a meaningful change/failure, not on a timer.

## Attribution

Successful explicit Read and strict literal `cat`, `sed -n N[,M]p`, `head`, `tail` shell readers can match reviewed registered skill paths. No command execution, expansion, content read or historical replay is performed by attribution. Dynamic commands, pipes, substitutions and mixed reader/non-reader chains are unknown. An observed read may be partial or empty and does not prove comprehension/application; explicit Skill calls and manual declarations remain separate. Old calls cannot be backfilled because their arguments were discarded. Source counters distinguish native-read, shell-literal and legacy evidence.

MCP namespaces are parsed from observed tool labels and shown separately even when unregistered. A namespace is not proof of a plugin, available connection or substitute. Generic `shell`/`other` catalog categories no longer create arbitrary substitution candidates.

## Check the effect

For a reviewed repeated task, keep the same task label and quality acceptance criterion, record before/after variants in Sessions, and compare enough real accepted sessions. Inspect model differences, collection gaps, unknown outcomes and commands first. A shared skill/helper is a hypothesis until actual tasks show less repeated manual work with equivalent quality. Test fixtures prove mechanics only; they are never inserted into the production journal. Shared files coordinate clients; no peer is automatically started.
