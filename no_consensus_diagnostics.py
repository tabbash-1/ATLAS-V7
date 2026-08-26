"""ATLAS NO_DIRECTIONAL_CONSENSUS diagnostics.

Research-only analysis for 2-2 vote ties. It reconstructs the contemporaneous
four-vote signature (price/EMA20, EMA20/EMA50, RSI50, 24h momentum) from the
WAIT tracker decision_context and studies later market direction. It never
breaks a Production tie, changes threshold 68, or authorizes execution.
"""

VERSION = 'NO_CONSENSUS_DIAGNOSTICS_V1'
HORIZONS = (1, 3, 6, 12, 24)
MIN_CONTEXT_SAMPLE = 20
MIN_CONFIRMING_HORIZONS = 2
MIN_DIRECTION_BIAS_PCT = 70.0
MATERIAL_MOVE_PCT = 1.0


def _f(v, default=None):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def has_context(row):
    c = row.get('decision_context') or {}
    required = ('ema20','ema50','rsi14','momentum_24h_pct')
    return all(_f(c.get(k)) is not None for k in required) and _f(row.get('wait_price')) is not None


def is_two_two(row):
    if str(row.get('reason') or '') != 'NO_DIRECTIONAL_CONSENSUS':
        return False
    c = row.get('decision_context') or {}
    lv = _f(c.get('direction_votes_long'))
    sv = _f(c.get('direction_votes_short'))
    return lv == 2 and sv == 2


def tie_signature(row):
    """Return the exact four binary vote polarities used by Production scoring."""
    if not has_context(row):
        return None
    c = row.get('decision_context') or {}
    px = _f(row.get('wait_price'))
    ema20 = _f(c.get('ema20')); ema50 = _f(c.get('ema50'))
    rsi = _f(c.get('rsi14')); mom = _f(c.get('momentum_24h_pct'))
    votes = (
        'P>L' if px >= ema20 else 'P<S',
        'E>L' if ema20 >= ema50 else 'E<S',
        'R>L' if rsi >= 50 else 'R<S',
        'M>L' if mom >= 0 else 'M<S',
    )
    return '|'.join(votes)


def _h(row, hours):
    return (row.get('horizons') or {}).get(f'{int(hours)}h') or {}


def outcome_direction(row, hours):
    change = _f(_h(row, hours).get('change_pct'))
    if change is None:
        return 'UNSETTLED'
    if change >= MATERIAL_MOVE_PCT:
        return 'UP'
    if change <= -MATERIAL_MOVE_PCT:
        return 'DOWN'
    return 'SMALL'


def _stats(rows, hours):
    counts = {'UP':0,'DOWN':0,'SMALL':0,'UNSETTLED':0}
    signed = []
    for r in rows:
        label = outcome_direction(r, hours)
        counts[label] += 1
        ch = _f(_h(r, hours).get('change_pct'))
        if ch is not None: signed.append(ch)
    directional = counts['UP'] + counts['DOWN']
    majority = None; bias = None
    if directional:
        if counts['UP'] > counts['DOWN']:
            majority = 'UP'; bias = 100.0 * counts['UP'] / directional
        elif counts['DOWN'] > counts['UP']:
            majority = 'DOWN'; bias = 100.0 * counts['DOWN'] / directional
        else:
            majority = 'TIED'; bias = 50.0
    return {
        'total': len(rows), 'settled': len(rows)-counts['UNSETTLED'],
        'counts': counts, 'material_directional_sample': directional,
        'majority_direction': majority,
        'direction_bias_pct': round(bias,2) if bias is not None else None,
        'avg_change_pct': round(sum(signed)/len(signed),4) if signed else None,
    }


def diagnose(payload):
    records = payload.get('records') if isinstance(payload,dict) else payload
    records = [r for r in (records or []) if isinstance(r,dict)]
    no_consensus = [r for r in records if str(r.get('reason') or '') == 'NO_DIRECTIONAL_CONSENSUS']
    tied = [r for r in no_consensus if is_two_two(r)]
    contextual = [r for r in tied if has_context(r) and tie_signature(r)]
    groups = {}
    for r in contextual:
        groups.setdefault(tie_signature(r), []).append(r)

    signatures = {}
    hypotheses = []
    for sig, rows in sorted(groups.items()):
        hs = {f'{h}h':_stats(rows,h) for h in HORIZONS}
        confirmations = []
        dirs = []
        for h in HORIZONS:
            st = hs[f'{h}h']
            if st['material_directional_sample'] >= MIN_CONTEXT_SAMPLE and (st['direction_bias_pct'] or 0) >= MIN_DIRECTION_BIAS_PCT and st['majority_direction'] in ('UP','DOWN'):
                confirmations.append(h); dirs.append(st['majority_direction'])
        same_direction = len(set(dirs)) == 1 if dirs else False
        eligible = len(confirmations) >= MIN_CONFIRMING_HORIZONS and same_direction
        row = {
            'records':len(rows),'horizons':hs,
            'confirming_horizons_h':confirmations,
            'shadow_hypothesis_eligible':eligible,
            'shadow_direction':dirs[0] if eligible else None,
            'production_applied':False,
        }
        signatures[sig] = row
        if eligible:
            hypotheses.append({'signature':sig,'direction':dirs[0],'confirming_horizons_h':confirmations,'records':len(rows),'production_applied':False})

    return {
        'schema':'ATLAS_NO_CONSENSUS_DIAGNOSTICS_V1','version':VERSION,
        'records_total':len(records),'no_consensus_records':len(no_consensus),
        'two_two_records':len(tied),'contextual_two_two_records':len(contextual),
        'context_coverage_pct':round(100*len(contextual)/len(tied),2) if tied else None,
        'signature_count':len(signatures),'signatures':signatures,
        'shadow_hypotheses':hypotheses,
        'guardrails':{
            'min_material_directional_sample_per_horizon':MIN_CONTEXT_SAMPLE,
            'min_confirming_horizons':MIN_CONFIRMING_HORIZONS,
            'min_direction_bias_pct':MIN_DIRECTION_BIAS_PCT,
            'material_move_pct':MATERIAL_MOVE_PCT,
        },
        'safety':{
            'research_only':True,'production_tie_breaking_enabled':False,
            'threshold_changed':False,'production_weights_changed':False,
            'execution_rules_changed':False,'can_execute':False,
        },
    }
