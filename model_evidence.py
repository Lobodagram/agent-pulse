"""Reported model identifiers, not guesses from UI, config or response text."""
from collections import defaultdict


def call_model(start, end):
    if any(p and p.get('model_conflicted') for p in (start,end)):
        return 'other', 'conflicting-event-models'
    a = start.get('model') if start else None
    b = end.get('model') if end else None
    a = None if a in (None, '', 'other') else a
    b = None if b in (None, '', 'other') else b
    if a and b and a != b:
        return 'other', 'conflicting-call-models'
    if a:
        return a, 'call-start'
    if b:
        return b, 'call-finish-only'
    return 'other', 'not-reported'


def model_history(calls, limit=100):
    """Segments are observed calls in one actor lane, never continuous model use.

    Unknown calls split segments. Overlapping different models are concurrent
    observations, not a proven switch. A switch time is an observation interval.
    """
    lanes = defaultdict(list)
    for c in calls:
        lanes[(c['provider'], c['session'], c['actor'])].append(c)
    segments = []
    for (provider, session, actor), items in lanes.items():
        items.sort(key=lambda c: (c['startedAt'] is None, c['startedAt'] or c['endedAt'] or 0, c['id']))
        previous = None
        active = None
        latest_end = None
        unresolved = False
        for c in items:
            model = c.get('model', 'other')
            at = c['startedAt'] if c['startedAt'] is not None else c['endedAt']
            valid = c['startedAt'] is not None and (c['endedAt'] is None or c['endedAt'] >= c['startedAt'])
            transition = 'first-observed'
            if previous:
                if model == 'other':
                    transition = 'unknown-gap'
                elif previous.get('model', 'other') == 'other':
                    transition = 'after-unknown'
                elif not valid or unresolved or previous['startedAt'] is None or previous['endedAt'] is None or previous['endedAt'] < previous['startedAt']:
                    transition = 'timing-unverified'
                elif latest_end is not None and at < latest_end:
                    transition = 'overlapping-observations'
                elif model != previous['model']:
                    transition = 'reported-change'
                else:
                    transition = 'same-reported-model'
            if active is None or active['model'] != model or transition not in ('same-reported-model','unknown-gap'):
                active = {'provider': provider, 'session': session, 'actor': actor,
                          'model': model, 'firstObservedAt': at, 'lastObservedAt': at,
                          'calls': 0, 'unknownOutcomes': 0, 'failed': 0,
                          'transition': transition,
                          'previousObservedAt': (previous['startedAt'] or previous['endedAt']) if previous else None,
                          'evidenceIds': []}
                segments.append(active)
            active['calls'] += 1
            active['failed'] += c['outcome'] == 'failed'
            active['unknownOutcomes'] += c['outcome'] in ('unknown', 'pending')
            active['lastObservedAt'] = at
            if len(active['evidenceIds']) < 10:
                active['evidenceIds'].append(c['id'])
            previous = c
            if c['endedAt'] is None:unresolved = True
            elif valid:latest_end = max(latest_end or c['endedAt'],c['endedAt'])
    segments.sort(key=lambda s: s['firstObservedAt'] or 0)
    return {'segments': segments[-limit:], 'truncated': len(segments) > limit,
            'knownModelCalls': sum(c.get('model', 'other') != 'other' for c in calls),
            'unknownModelCalls': sum(c.get('model', 'other') == 'other' for c in calls),
            'reportedChanges': sum(s['transition'] == 'reported-change' for s in segments),
            'coverage': 'native call identifiers only; observation times, not exact UI switch times; unknowns never inherited'}
