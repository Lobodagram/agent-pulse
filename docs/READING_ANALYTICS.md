# Reading analytics

[Русский](READING_ANALYTICS.ru.md)

Quota/token counters do not establish tool-event coverage. The five views answer different questions:

| View | Source | Empty-value meaning |
| --- | --- | --- |
| Overview | Native usage counters, aggregate history, journal coverage | Missing tokens are unknown; quota reset is not subscription renewal. |
| Workflows | Observed calls and conservative repetition thresholds | Calls may exist without a qualifying pattern. No finding does not mean an inactive observer. |
| Sessions | Received starts/finishes and native model fields | Missing finish/result/model stays pending or unknown. Previous/Next continues long sessions. |
| Capabilities | Reviewed catalog, supported evidence and tool counts | No confirmed events is not proof of non-use. Tools appear first; Mac can expand unobserved catalog entries. |
| Compare | Manually labelled tasks, variants and acceptance | Empty groups mean insufficient reviewed evidence. At least three sessions per variant; comparable difficulty/model settings still need review. |

The timestamp is the last received call. Silence can mean an idle client. Paired/received ratios describe received events only; invisible tools have no known denominator. Rejections are cumulative recorded rejections, not all lost activity.

## Attribution limits

Findings prioritize repeated failures, reads and identical requests before broad category sequences. Todo/plan updates, waits and clarification requests remain in the journal but do not generate automation candidates and act as sequence barriers. Exclusion from candidates neither deletes events nor proves wasted time.

The review pack counts typed, unknown and bookkeeping operations. Allowlisted checksum/archive/plist/HTTP commands, GitHub CI tools and mesh/release/context helpers refine operation families. Names do not prove provenance, successful use or MCP availability. Known historical tool names can be projected again; unknown shell arguments cannot be recovered. Use fresh finding IDs after reclassification; a disappeared card does not prove a workflow was fixed.

The detector recognises exact registered locators in Read/read_file/cat_file, explicit Skill/use_skill identifiers and matching registered MCP namespaces. Since 0.7.0, successful strict literal cat/sed/head/tail readers can match registered paths, without expansion or historical replay. Unregistered MCP namespaces appear separately and as tools; a namespace does not establish a plugin or live connection. Reading a skill does not establish application of its instructions. Do not delete a skill because its use is unconfirmed.

## Continue a long session

Mac/Windows use pages of 500 calls. MCP defaults to 50, allows 1–100. A signed local cursor continues or revisits the same snapshot. No prompts, arguments or results are included. The model overview describes the whole bounded session snapshot; calls show the current page.

```sh
agent-pulse journal --action session --session HASHED_SESSION_ID --limit 100
agent-pulse journal --action session --session HASHED_SESSION_ID --limit 100 --cursor RETURNED_NEXT_CURSOR --file page.json
```

Use `cursor` to revisit and `nextCursor` to continue. The file contains one page, not a complete automatic export. Without installation use `python3 collector.py` or the packaged helper. MCP pulse_session accepts sessionId, optional cursor and limit.

New events after the first read are excluded. If old evidence changes (late completion, model conflict/reconciliation, retention), continuation is rejected; reopen for a fresh snapshot. Limits: 30 days and 20,000 received events, with an event-limit flag. Never-collected events cannot be recovered. General report/export recentCalls is a 100-call preview, not full history.

Compact Mac menu cycles full uppercase client names without a page counter. Windows summaries use the same names; native tray tooltip length remains bounded.

[Reviewed decisions, recheck states and bounded human exports](IMPROVEMENT_LOOP.md).

## Daily token details

Mac: Tokens; Windows: Daily tokens. The Mac chart uses readable units rather than scientific notation. Hover previews a UTC day, clicking pins it, and the date selector works without a pointer. Exact counters and coverage appear per enabled client; no entry means unknown, not zero. These daily sources do not expose hourly counters. Local Codex backlog recovery skips older unread bytes within the existing bounded read; the baseline is reset so skipped cumulative usage cannot be charged to today. A source warning records the gap. Native account-day totals take precedence over overlapping local counters.
