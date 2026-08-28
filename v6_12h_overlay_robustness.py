#!/usr/bin/env python3
"""Cross-symbol robustness test for frozen Candidate C as a 12h-only overlay.

This does not revise Candidate C. It asks whether the already-frozen formula's
12h chronological-holdout improvement survives removing each symbol in turn.
Passing only permits prospective shadow observation; it never changes Production.
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from v6_shadow_replay import independent, ret, metrics, baseline, score_C

SRC = Path('status/wait-outcomes.json')
OUT = Path('status/v6-12h-overlay-robustness.json')
HORIZON = '12h'


def ranked(rows, fn, k):
    eligible = [r for r in rows if ret(r, HORIZON) is not None]
    return sorted(eligible, key=lambda r: (fn(r), baseline(r)), reverse=True)[:k]


def compare(rows, k):
    bsel = ranked(rows, baseline, k)
    csel = ranked(rows, score_C, k)
    b = metrics(bsel, HORIZON)
    c = metrics(csel, HORIZON)
    delta = {
        'win_rate_delta_pp': round((c.get('win_rate_pct') or 0) - (b.get('win_rate_pct') or 0), 2),
        'mean_delta_pct': round((c.get('mean_pct') or 0) - (b.get('mean_pct') or 0), 4),
        'median_delta_pct': round((c.get('median_pct') or 0) - (b.get('median_pct') or 0), 4),
        'p10_delta_pct': round((c.get('p10_pct') or 0) - (b.get('p10_pct') or 0), 4),
        'large_loss_delta_pp': round((c.get('loss_rate_le_minus_2pct') or 0) - (b.get('loss_rate_le_minus_2pct') or 0), 2),
    }
    quality_nonworse = delta['win_rate_delta_pp'] >= 0 and delta['mean_delta_pct'] >= 0 and delta['median_delta_pct'] >= 0
    downside_nonworse = delta['large_loss_delta_pp'] <= 0
    return {
        'baseline': b,
        'candidate': c,
        'delta': delta,
        'quality_nonworse': quality_nonworse,
        'downside_nonworse': downside_nonworse,
        'candidate_symbols': dict(sorted(Counter(str(r.get('symbol') or '').upper() for r in csel).items())),
    }


def main():
    raw = json.loads(SRC.read_text()).get('records') or []
    eps = sorted(independent(raw), key=lambda r: r.get('_episode_time') or '')
    cut = max(1, int(len(eps) * 0.70))
    test = eps[cut:]
    eligible = [r for r in test if ret(r, HORIZON) is not None]
    symbols = sorted({str(r.get('symbol') or '').upper() for r in eligible if r.get('symbol')})

    ks = sorted(set(k for k in (3, 5, 8, max(1, len(eligible)//2)) if k <= len(eligible)))
    overall = {str(k): compare(test, k) for k in ks}

    # Jackknife: remove one symbol at a time and compare at equal coverage.
    jackknife = {}
    jk_quality = jk_safe = jk_total = 0
    for sym in symbols:
        rows = [r for r in test if str(r.get('symbol') or '').upper() != sym]
        n = sum(ret(r, HORIZON) is not None for r in rows)
        if n < 3:
            continue
        k = min(5, max(3, n // 2))
        k = min(k, n)
        cell = compare(rows, k)
        jackknife[sym] = {'eligible_n': n, 'k': k, **cell}
        jk_total += 1
        jk_quality += int(cell['quality_nonworse'])
        jk_safe += int(cell['downside_nonworse'])

    quality_rate = (jk_quality / jk_total) if jk_total else 0.0
    safe_rate = (jk_safe / jk_total) if jk_total else 0.0

    # Concentration guard on candidate top-5 (or largest available cohort <=5).
    concentration_k = min(5, len(eligible))
    ctop = ranked(test, score_C, concentration_k) if concentration_k else []
    counts = Counter(str(r.get('symbol') or '').upper() for r in ctop)
    max_share = (max(counts.values()) / len(ctop)) if ctop else 1.0

    overall_good = sum(int(v['quality_nonworse']) for v in overall.values()) >= max(1, int(len(overall) * 0.60 + 0.999))
    overall_safe = sum(int(v['downside_nonworse']) for v in overall.values()) >= max(1, int(len(overall) * 0.60 + 0.999))
    pass_test = bool(
        len(eligible) >= 15
        and overall_good
        and overall_safe
        and jk_total >= 4
        and quality_rate >= 0.60
        and safe_rate >= 0.60
        and max_share <= 0.60
    )

    report = {
        'schema': 'ATLAS_V6_12H_OVERLAY_ROBUSTNESS_V1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'candidate': 'C_VOLUME_PLUS_RS_FROZEN',
        'scope': '12H_ONLY',
        'split': {'train_fraction': 0.70, 'test_fraction': 0.30, 'test_n': len(test), 'eligible_12h_n': len(eligible)},
        'overall_equal_coverage': overall,
        'jackknife_by_removed_symbol': jackknife,
        'summary': {
            'jackknife_cells': jk_total,
            'jackknife_quality_nonworse_pct': round(quality_rate * 100, 2),
            'jackknife_downside_nonworse_pct': round(safe_rate * 100, 2),
            'candidate_top_cohort_max_symbol_share_pct': round(max_share * 100, 2),
        },
        'decision': 'ADVANCE_TO_PROSPECTIVE_12H_SHADOW' if pass_test else 'REJECT_OR_REVISE_12H_OVERLAY',
        'guardrails': {
            'research_only': True,
            'production_threshold_changed': False,
            'production_score_changed': False,
            'auto_promotion_enabled': False,
            'candidate_formula_changed': False,
        },
        'note': 'Candidate C is not approved as a general V6 replacement. This test only evaluates whether its previously observed 12h benefit is cross-symbol robust enough for prospective shadow observation.'
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'eligible_12h_n': len(eligible), 'jackknife_cells': jk_total, 'decision': report['decision']}))


if __name__ == '__main__':
    main()
