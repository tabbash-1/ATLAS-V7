#!/usr/bin/env python3
"""Scope an offline path-settlement report into plan-shadow vs executable cohorts.

A Production-qualified conditional setup is not a filled/executable trade. This
post-processor prevents plan-quality research from being mislabeled as realized R.
It never alters Production, thresholds, alerts, or execution.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATH = ROOT / 'status/production-path-settlement-latest.json'
SCHEMA = 'ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V3_EXECUTION_SCOPED'


def summarize(rows):
    terminal = [r for r in rows if r.get('terminal') and r.get('r_multiple') is not None]
    vals = [float(r['r_multiple']) for r in terminal]
    wins = [x for x in vals if x > 0]
    losses = [x for x in vals if x < 0]
    pos, neg = sum(wins), abs(sum(losses))
    by_dir = {}
    for direction in ('LONG','SHORT'):
        dv = [float(r['r_multiple']) for r in terminal if (r.get('geometry') or {}).get('direction') == direction]
        by_dir[direction] = {
            'n': len(dv),
            'net_r': round(sum(dv),4),
            'avg_r': round(sum(dv)/len(dv),4) if dv else None,
            'win_rate_pct': round(100*sum(x>0 for x in dv)/len(dv),2) if dv else None,
        }
    providers = {}
    for r in rows:
        src = r.get('market_source')
        if src: providers[src] = providers.get(src,0)+1
    return {
        'episodes': len(rows), 'terminal': len(terminal), 'open_or_error': len(rows)-len(terminal),
        'wins': len(wins), 'losses': len(losses),
        'win_rate_pct': round(100*len(wins)/len(terminal),2) if terminal else None,
        'net_r': round(sum(vals),4), 'average_r': round(sum(vals)/len(vals),4) if vals else None,
        'profit_factor_r': round(pos/neg,4) if neg > 0 else None,
        'by_direction': by_dir,
        'market_data_errors': sum(r.get('status') == 'MARKET_DATA_ERROR' for r in rows),
        'ambiguous': sum(r.get('status') == 'AMBIGUOUS' for r in rows),
        'provider_counts': providers,
    }


def execution_eligible(row):
    # Historical snapshots explicitly recorded execution_ready at the same instant
    # the canonical geometry was frozen. Only these rows can represent executable
    # Production decisions. All others remain plan-shadow research.
    return row.get('execution_ready_at_capture') is True


def main():
    raw = json.loads(PATH.read_text())
    records = list(raw.get('records') or [])
    executable = [r for r in records if execution_eligible(r)]
    conditional = [r for r in records if not execution_eligible(r)]
    raw['upstream_schema'] = raw.get('schema')
    raw['schema'] = SCHEMA
    raw['scoped_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    raw['scope_semantics'] = {
        'plan_shadow': 'ALL_PRODUCTION_QUALIFIED_CANONICAL_PLANS; NOT REALIZED TRADES',
        'execution_ready': 'PRODUCTION_QUALIFIED AND execution_ready_at_capture=true',
        'realized_r_authority': 'EXECUTION_READY_ONLY',
    }
    raw['plan_shadow_summary'] = summarize(records)
    raw['execution_ready_summary'] = summarize(executable)
    raw['conditional_not_executed_summary'] = summarize(conditional)
    raw['summary'] = raw['execution_ready_summary']
    raw['realized_r_scope'] = 'EXECUTION_READY_ONLY'
    raw['plan_shadow_is_realized_r'] = False
    raw['research_only'] = True
    raw['live_execution'] = False
    raw['can_override_production'] = False
    raw['can_change_threshold'] = False
    raw['production_threshold_unchanged'] = 68
    PATH.write_text(json.dumps(raw,indent=2,sort_keys=True))
    print(json.dumps({
        'schema': raw['schema'],
        'plan_shadow': raw['plan_shadow_summary'],
        'execution_ready': raw['execution_ready_summary'],
        'conditional_not_executed': raw['conditional_not_executed_summary'],
    },indent=2))

if __name__ == '__main__':
    main()
