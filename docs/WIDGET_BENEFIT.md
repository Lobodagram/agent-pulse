# Widget benefit evidence

[Русский](WIDGET_BENEFIT.ru.md)

The floating widget has a **Pulse benefit** disclosure beneath each client's daily counters. It starts collapsed. Click to expand or collapse that client independently; the window adjusts its height. The monochrome menu bar and Windows compact quota strip retain their existing presentation. Refresh updates the block with the current local evidence; the regular full refresh is every five minutes.

- **30d Skill / reads**: all observed native Skill calls, including failed or pending calls, and successful exact catalog skill-file reads. Activity appears even without a Pulse finding link. The macOS tooltip separates successful matched and unmatched Skill calls. Unknown identities are counted without retaining names. Reading does not establish application or version. Empty observations and missing legacy fields are explicitly labelled; non-use is never established.
- **MCP calls / helpers**: received calls with a valid MCP namespace, independent of catalog registration or outcome, and explicit helper receipt runs in the retained 30-day window. Helper counters are scoped to the actual reporting client; failed/pending/conflicting runs remain in the denominator. The tooltip reports known helper results. Neither namespace nor a receipt proves live connection, accepted work or savings.
- **Pulse improvements**: distinct registered assets explicitly linked to a reviewed finding; versions are deduplicated. Unlinked registrations are excluded from this count, but their observed activity remains above. Without links it says improvements are not recorded; with links but no reviewed selections it says awaiting review. Only with reviewed selections are declared task applications shown. These are manual assertions, not automatically proven creation or implementation. The tooltip retains kind breakdown and linked native invocation counters.
- **Model requests / tokens**: differences per accepted result in one explicitly pinned comparison. In **Analytics → Compare**, choose the client, task label, before and after variants, then **Pin pair in widget**. Clear the pair there too. Pulse does not choose the best-looking comparison. Full native receipts, at least three tasks per variant, matching observed cohorts and reviewed quality are required by the same comparison gates as the detailed report. All selected attempts, including failed/rework results, remain in the denominator calculation. Down arrows mean reduction; up arrows mean increased consumption; zero and unavailable are distinct. These are observational differences, not proof that Pulse caused them. Task difficulty and model settings still require review.
- **Model cache**: local cached-input / input tokens for the current UTC day, with partial coverage. It is explicitly the model's cache, not credited to Pulse. Unreported cache displays a dash and “not reported”. With no selected comparison the effect says “not evaluated”; with insufficient comparison data it says so. True measured zero remains 0% when comparison gates pass.

Clicking the expanded metrics opens Analytics. On macOS its tooltip includes the selected task/variant names, sample sizes and limitations. No percentage estimates subscription allowance, money saved or a universal productivity score. Model requests are never inferred from tool-call counts.

Selection persists in the existing local journal (`widget_comparison`), one bounded label/variant pair per client. It survives restart but stores no conversation, prompts or tool payloads. Re-evaluation uses all retained reviewed tasks, not just the 100-row report preview. When tasks expire or evidence becomes insufficient, percentages disappear rather than retaining a stale result.

CLI (local metadata only):

```sh
python3 collector.py journal --action widget-comparison --provider codex --label release-check --before before --after after
python3 collector.py journal --action widget-comparison --provider codex
```

The second command clears the client selection without changing any task, finding or asset evidence.

The [current benefit screenshot](screenshots/benefit-en.png) shows the five-row 0.14.6 presentation with invented DEMO data, including an unevaluated effect.
