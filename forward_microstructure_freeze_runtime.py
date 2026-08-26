"""Freeze decision-time microstructure context into every new Forward row.

This wrapper sits immediately before the Forward archive write. It uses only
Smart-Money snapshots with captured_at_ms <= the Forward timestamp, so later
market information and forward returns cannot enter the frozen entry context.
It does not modify Production scoring or execution.
"""
from __future__ import annotations

import copy
import urllib.parse
from collections import Counter

import microstructure_memory
import microstructure_walkforward
import prospective_microstructure_cohort

VERSION = 'ATLAS_FORWARD_MICROSTRUCTURE_FREEZE_V1_PRIOR_ONLY'
LOOKBACK_MS = 24 * 60 * 60 * 1000

STATE = {
    'installed': False,
    'frozen_rows': 0,
    'errors': 0,
    'last_error': None,
    'last_frozen_at': None,
    'last_forward_id': None,
    'last_relation': None,
    'last_consensus': None,
    'relation_counts_since_install': {},
    'consensus_counts_since_install': {},
    'research_only': True,
    'live_execution': False,
    'can_override_production': False,
    'cached_only': True,
}
_RELATIONS = Counter()
_CONSENSUS = Counter()


def _ts(row):
    try:
        return int((row or {}).get('captured_at_ms') or 0)
    except Exception:
        return 0


def _compact_memory(memory):
    memory = memory or {}
    windows = memory.get('windows') or {}
    compact_windows = {}
    if isinstance(windows, dict):
        for key, value in windows.items():
            if not isinstance(value, dict):
                continue
            compact_windows[str(key)] = {
                k: value.get(k)
                for k in ('ready','bias','score','n','funding_mean','oi_change_mean_pct','taker_ratio_mean','orderbook_imbalance_mean')
                if k in value
            }
    return {
        'consensus': memory.get('consensus'),
        'ready_windows': int(memory.get('ready_windows') or 0),
        'windows': compact_windows,
    }


def enrich_row(collector, row):
    out = copy.deepcopy(row)
    ts = _ts(out)
    symbol = str(out.get('symbol') or '').upper().replace('BINANCE:', '')
    direction = str(out.get('direction') or '').upper()
    if ts <= 0 or not symbol or direction not in ('LONG', 'SHORT'):
        return out

    prior = []
    for smart in collector.read_all():
        if not isinstance(smart, dict):
            continue
        if str(smart.get('symbol') or '').upper().replace('BINANCE:', '') != symbol:
            continue
        sts = _ts(smart)
        if ts - LOOKBACK_MS <= sts <= ts:
            prior.append(smart)
    prior.sort(key=_ts)

    memory = microstructure_memory.analyze(symbol, prior, now_ms=ts)
    consensus = memory.get('consensus') or 'INSUFFICIENT'
    relation = microstructure_walkforward.classify_relation(direction, consensus)

    out['microstructure_freeze_schema'] = VERSION
    out['microstructure_consensus_at_entry'] = consensus
    out['microstructure_relation_at_entry'] = relation
    out['microstructure_ready_windows_at_entry'] = int(memory.get('ready_windows') or 0)
    out['microstructure_source_rows_prior_only_at_entry'] = len(prior)
    out['microstructure_memory_at_entry'] = _compact_memory(memory)
    out['microstructure_outcome_known_at_entry'] = False
    out['microstructure_future_data_allowed_at_entry'] = False
    out['microstructure_can_override_production'] = False
    return out


def _status_payload(collector=None):
    cohort = getattr(collector, 'PROSPECTIVE_MICROSTRUCTURE_COHORT_STATE', {}) if collector is not None else {}
    return {
        'ok': bool(STATE.get('installed')),
        'version': VERSION,
        'cached_only': True,
        'background_refresh_triggered': False,
        'archive_read_triggered_by_request': False,
        'outcome_read_triggered_by_request': False,
        'research_only': True,
        'live_execution': False,
        'can_override_production': False,
        'state': copy.deepcopy(STATE),
        'prospective_cohort': {k: cohort.get(k) for k in ('status','registration_locked','cohort_hash','cohort_start_ms','cohort_start_at','last_error')},
    }


def install(collector):
    if STATE.get('installed'):
        return STATE

    # Critical ordering: register and lock the prospective cohort BEFORE
    # replacing _forward_write. Therefore the first eligible frozen row cannot
    # predate the cohort manifest in this process.
    cohort_state = prospective_microstructure_cohort.install(collector)
    if cohort_state.get('status') != 'PREREGISTERED' or not cohort_state.get('registration_locked'):
        STATE['last_error'] = 'PROSPECTIVE_COHORT_NOT_PREREGISTERED'
        return STATE

    original_write = collector._forward_write

    def frozen_write(row):
        try:
            enriched = enrich_row(collector, row)
            original_write(enriched)
            relation = enriched.get('microstructure_relation_at_entry') or 'UNCLASSIFIED'
            consensus = enriched.get('microstructure_consensus_at_entry') or 'UNKNOWN'
            _RELATIONS[relation] += 1
            _CONSENSUS[consensus] += 1
            STATE['frozen_rows'] += 1
            STATE['last_error'] = None
            STATE['last_frozen_at'] = enriched.get('captured_at')
            STATE['last_forward_id'] = enriched.get('id')
            STATE['last_relation'] = relation
            STATE['last_consensus'] = consensus
            STATE['relation_counts_since_install'] = dict(sorted(_RELATIONS.items()))
            STATE['consensus_counts_since_install'] = dict(sorted(_CONSENSUS.items()))
        except Exception as exc:
            # Fail open for collection only: never lose a Forward observation
            # because the research-only enrichment layer had an error.
            STATE['errors'] += 1
            STATE['last_error'] = f'{type(exc).__name__}: {exc}'
            original_write(row)

    collector._forward_write = frozen_write
    collector.FORWARD_MICROSTRUCTURE_FREEZE_STATE = STATE

    original_get = collector.Handler.do_GET
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/api/research/forward-microstructure-freeze':
            return self._json(_status_payload(collector))
        return original_get(self)
    collector.Handler.do_GET = do_GET

    STATE['installed'] = True
    return STATE
