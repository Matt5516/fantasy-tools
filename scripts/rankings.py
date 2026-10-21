"""Pure helpers for the weekly position rankings pages (week-N-<pos>-rankings). Unit-tested in _tests/rankings.test.py."""

OUT = ('Out', 'IR', 'PUP', 'Sus')
POS_LABEL = {'qb': 'QB', 'rb': 'RB', 'wr': 'WR', 'te': 'TE', 'flex': 'Flex', 'kicker': 'Kicker', 'defense': 'Defense'}


def rank_rows(items, fmt='ppr'):
    """Players with a projection who are not ruled out, best first (ties broken by name so the order is stable)."""
    ok = [p for p in items if p.get('proj') and p['proj'].get(fmt) is not None and p.get('inj') not in OUT]
    return sorted(ok, key=lambda p: (-p['proj'][fmt], p['n']))


def tier_breaks(values, min_gap=0.5, factor=1.5, max_breaks=7):
    """Indexes i where a new tier starts at position i. `values` are descending projections.
    A break needs a gap to the previous player of at least max(min_gap, factor x the average gap); if more than max_breaks
    qualify, the largest gaps win (earlier one first on a tie)."""
    if len(values) < 3: return []
    gaps = [round(values[i - 1] - values[i], 4) for i in range(1, len(values))]
    thr = max(min_gap, factor * sum(gaps) / len(gaps))
    cand = [(g, i + 1) for i, g in enumerate(gaps) if g >= thr]
    cand = sorted(cand, key=lambda t: (-t[0], t[1]))[:max_breaks]
    return sorted(i for _, i in cand)


def tier_numbers(n, breaks):
    """Tier number (1-based) for each of n positions given the break indexes."""
    out, t, bs = [], 1, set(breaks)
    for i in range(n):
        if i in bs: t += 1
        out.append(t)
    return out


def tier_groups(n, breaks):
    """(start, end_exclusive) per tier."""
    edges = [0] + list(breaks) + [n]
    return [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]


def top_names(rows, k=3):
    """'A, B and C' for the first k rows."""
    names = [p['n'] for p in rows[:k]]
    if not names: return ''
    if len(names) == 1: return names[0]
    return ', '.join(names[:-1]) + ' and ' + names[-1]


def opp_label(opp, team):
    """'@CHI' (away), 'CHI' (home), 'Bye' when the schedule is known but the team has no game, '' when there is no schedule."""
    if not opp: return ''
    return opp.get(team) or 'Bye'


def opp_words(label):
    """Plain-English form of an opponent label for FAQ answers."""
    if not label: return ''
    if label == 'Bye': return 'on a bye'
    return ('at ' + label[1:]) if label.startswith('@') else ('vs ' + label)


def target_week_slugs(week, first_week, kinds):
    """Old-week slugs that become redirects to the current week's pages."""
    return [f'week-{w}-{k}-rankings' for w in range(first_week, week) for k in kinds]


def fmt_pts(v):
    return '—' if v is None else f'{v:.1f}'
