"""ATLAS historical microstructure replay feature builder.

Builds *features only* from persistent data that existed at or before each
Forward timestamp. It never reads forward returns, settlements or outcome files.
The resulting dataset is retrospective research evidence, not frozen-forward
proof, and is meant to be frozen before any outcome evaluation occurs.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

import microstructure_memory
import microstructure_walkforward

VERSION = 'ATLAS_HISTORICAL_MICROSTRUCTURE_REPLAY_V1_PRIOR_ONLY_FEATURES'
LOOKBACK_MS = 24 * 3600 * 1000


def _ts(row):
    try:
        return int((row or {}).get('captured_at_ms') or 0)
    except Exception:
        return 0


def _direction(row):
    d = str((row or {}).get('direction') or '').upper()
    return d if d in ('LONG', 'SHORT') else None


def _canonical_hash(rows):
    payload = json.dumps(rows, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def build_features(forward_rows, smart_rows):
    """Return deterministic outcome-free replay rows.

    Smart-Money rows are filtered to same symbol and timestamp <= Forward time;
    no later snapshot can enter any rolling 4h/12h/24h window.
    """
    smart_by_symbol = {}
    for row in smart_rows or []:
        if not isinstance(row, dict) or _ts(row) <= 0 or not row.get('symbol'):
            continue
        sym = str(row.get('symbol')).upper().replace('BINANCE:', '')
        smart_by_symbol.setdefault(sym, []).append(row)
    for rows in smart_by_symbol.values():
        rows.sort(key=_ts)

    out = []
    for f in forward_rows or []:
        if not isinstance(f, dict):
            continue
        ts = _ts(f)
        direction = _direction(f)
        symbol = str(f.get('symbol') or '').upper().replace('BINANCE:', '')
        forward_id = str(f.get('id') or '')
        if ts <= 0 or not direction or not symbol or not forward_id or f.get('entry') is None:
            continue
        # Outcome fields on Forward rows are deliberately never copied/read here.
        prior = [
            r for r in smart_by_symbol.get(symbol, [])
            if ts - LOOKBACK_MS <= _ts(r) <= ts
        ]
        memory = microstructure_memory.analyze(symbol, prior, now_ms=ts)
        consensus = memory.get('consensus') or 'INSUFFICIENT'
        relation = microstructure_walkforward.classify_relation(direction, consensus)
        out.append({
            'schema': 'ATLAS_HISTORICAL_MICROSTRUCTURE_FEATURE_ROW_V1',
            'forward_id': forward_id,
            'forward_captured_at_ms': ts,
            'symbol': symbol,
            'direction': direction,
            'entry': f.get('entry'),
            'score': f.get('final_score', f.get('champion_score')),
            'regime': f.get('regime'),
            'rr_tp2': f.get('rr_tp2'),
            'microstructure_memory': memory,
            'consensus': consensus,
            'relation_to_signal': relation,
            'ready_windows': int(memory.get('ready_windows') or 0),
            'source_smart_rows_prior_only': len(prior),
            'outcome_known_to_builder': False,
            'retrospective_reconstruction': True,
            'forward_proof_equivalent': False,
            'research_only': True,
            'can_override_production': False,
        })
    out.sort(key=lambda x: (int(x['forward_captured_at_ms']), x['forward_id']))
    return out


def report(forward_rows, smart_rows):
    rows = build_features(forward_rows, smart_rows)
    ready = [x for x in rows if int(x.get('ready_windows') or 0) >= 2]
    by_relation = Counter(x.get('relation_to_signal') for x in ready)
    by_consensus = Counter(x.get('consensus') for x in ready)
    by_symbol = Counter(x.get('symbol') for x in ready)
    first_ms = min((x['forward_captured_at_ms'] for x in rows), default=None)
    last_ms = max((x['forward_captured_at_ms'] for x in rows), default=None)
    feature_hash = _canonical_hash(rows)
    return {
        'schema': VERSION,
        'research_only': True,
        'live_execution': False,
        'outcomes_read': False,
        'forward_return_fields_read': False,
        'settlement_files_read': False,
        'future_data_allowed': False,
        'backfill_claimed_as_frozen_forward': False,
        'retrospective_reconstruction': True,
        'forward_proof_equivalent': False,
        'feature_rows': len(rows),
        'ready_two_or_more_windows': len(ready),
        'ready_for_retrospective_evaluation': len(ready) >= 60,
        'first_forward_ms': first_ms,
        'last_forward_ms': last_ms,
        'relation_counts_ready': dict(sorted(by_relation.items())),
        'consensus_counts_ready': dict(sorted(by_consensus.items())),
        'symbol_counts_ready': dict(sorted(by_symbol.items())),
        'feature_dataset_sha256': feature_hash,
        'method': 'CURRENT_MICROSTRUCTURE_MODEL_REPLAYED_ONLY_ON_RECORDED_PRE_TIMESTAMP_SMART_MONEY',
        'rows': rows,
    }
