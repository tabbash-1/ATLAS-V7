"""Reliability wrapper for ATLAS HTF scenario evidence collection.

Adds bounded retry for Render decision reads and protects last-good canonical
evidence: if zero live decisions can be read, the run fails before save().
Partial coverage remains explicit and auditable.
"""
from __future__ import annotations

import json
import time

import scenario_evidence_pipeline as p

VERSION = 'SCENARIO_EVIDENCE_RELIABLE_RUNNER_V1'
RETRY_DELAYS = (0, 2, 4, 8, 12, 16)


def fetch_decision_retry(symbol, delays=RETRY_DELAYS, sleeper=time.sleep):
    last = None
    for delay in delays:
        if delay:
            sleeper(delay)
        try:
            return p.fetch_decision(symbol)
        except Exception as exc:
            last = exc
    raise RuntimeError(f'ATLAS decision fetch failed after {len(delays)} attempts for {symbol}: {last}')


def coverage(successful, total):
    total = int(total or 0)
    successful = int(successful or 0)
    pct = round(100.0 * successful / total, 2) if total else 0.0
    status = 'FULL' if total and successful == total else ('PARTIAL' if successful else 'FAILED')
    return status, pct


def run_once(now=None, fetcher=fetch_decision_retry, saver=p.save):
    stamp = (now or p.now_utc()).isoformat()
    records = p.load_records()
    captured = 0
    deduped = 0
    successful = 0
    decision_errors = []
    settlement_errors = []

    for symbol in p.SYMBOLS:
        try:
            decision = fetcher(symbol)
            successful += 1
            candidate = p.capture_from_decision(decision, captured_at=stamp)
            if candidate:
                if p.dedupe_append(records, candidate):
                    captured += 1
                else:
                    deduped += 1
        except Exception as exc:
            decision_errors.append({'symbol': symbol, 'error': str(exc)})

    status, pct = coverage(successful, len(p.SYMBOLS))
    if successful == 0:
        raise RuntimeError(
            'Scenario evidence collection aborted: zero successful ATLAS decision reads; '
            'canonical last-good evidence was not overwritten. Errors=' + json.dumps(decision_errors, separators=(',', ':'))
        )

    settled = []
    for row in records:
        try:
            settled.append(p.settle_record(row, now=now))
        except Exception as exc:
            copy = dict(row)
            copy['last_settlement_error'] = str(exc)
            settled.append(copy)
            settlement_errors.append({
                'scenario_id': row.get('scenario_id'), 'symbol': row.get('symbol'), 'error': str(exc)
            })

    snapshot = p.calibration_snapshot(settled, captured_at=stamp)
    snapshot['collector'] = {
        'symbols': list(p.SYMBOLS),
        'successful_decisions': successful,
        'failed_decisions': len(decision_errors),
        'coverage_pct': pct,
        'collector_status': status,
        'captured_new': captured,
        'deduped': deduped,
        'records': len(settled),
        'decision_errors': decision_errors,
        'settlement_errors': settlement_errors,
    }
    saver(settled, snapshot)
    return snapshot


if __name__ == '__main__':
    result = run_once()
    c = result['collector']
    print(json.dumps({
        'ok': c['successful_decisions'] > 0,
        'pipeline_version': p.VERSION,
        'runner_version': VERSION,
        'collector': c,
        'research_only': True,
        'live_execution': False,
    }, indent=2))
