# Review → implement → observe

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
