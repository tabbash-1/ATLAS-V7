#!/usr/bin/env python3
"""Probe actual historical raw indicator coverage for V6 LONG rows."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base

OUT = Path('status/long-v7-raw-feature-schema.json')


def flatten_paths(obj, prefix=''):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f'{prefix}.{k}' if prefix else str(k)
            out.append(p)
            out.extend(flatten_paths(v, p))
    return out


def main():
    snaps = base.load_snapshots()
    total = 0
    with_indicators = 0
    paths = Counter()
    examples = {}
    versions = Counter()
    for ts, snap in snaps:
        for symbol, d in (snap.get('decisions') or {}).items():
            d = d or {}
            version = str(d.get('scoring_version') or '')
            direction = str(d.get('candidate_direction') or '').upper()
            if not version.startswith(base.V6_PREFIX) or direction != 'LONG':
                continue
            total += 1
            versions[version] += 1
            ind = d.get('indicators')
            if isinstance(ind, dict):
                with_indicators += 1
                for p in flatten_paths(ind):
                    paths[p] += 1
                if not examples:
                    examples = ind
    rows = [
        {
            'path': p,
            'rows_present': n,
            'coverage_pct': round(100.0*n/total, 2) if total else 0.0,
        }
        for p, n in sorted(paths.items(), key=lambda x: (-x[1], x[0]))
    ]
    report = {
        'schema': 'ATLAS_LONG_V7_RAW_FEATURE_SCHEMA_PROBE_V1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'v6_long_decision_rows': total,
        'rows_with_indicators': with_indicators,
        'indicator_coverage_pct': round(100.0*with_indicators/total, 2) if total else 0.0,
        'indicator_paths': rows,
        'first_indicator_example': examples,
        'scoring_versions': dict(versions),
        'research_only': True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
