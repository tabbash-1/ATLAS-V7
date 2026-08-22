#!/usr/bin/env python3
import os, threading, time

import atlas_runtime_server as runtime

atlas = runtime.atlas

RESEARCH_SAMPLE_MIN_SCORE = float(os.environ.get('ATLAS_RESEARCH_SAMPLE_MIN_SCORE', '50'))
RESEARCH_SAMPLE_MAX_PER_CYCLE = max(1, min(7, int(os.environ.get('ATLAS_RESEARCH_SAMPLE_MAX_PER_CYCLE', '3'))))
RESEARCH_LANE_STATE = {
    'enabled': True,
    'min_score': RESEARCH_SAMPLE_MIN_SCORE,
    'max_per_cycle': RESEARCH_SAMPLE_MAX_PER_CYCLE,
    'cycles': 0,
    'scored_directional': 0,
    'shadow_directional_proxies': 0,
    'signal_qualified': 0,
    'research_selected': 0,
    'research_stored': 0,
    'research_deduped': 0,
    'last_top_scores': [],
    'last_selected': [],
    'last_error': None,
    'last_success_at': None,
}
runtime.CLOUD_RUNTIME_STATE['research_lane'] = RESEARCH_LANE_STATE


def shadow_research_score_symbol(symbol, btc_ks):
    """Classify neutral/choppy states for observation only.

    This is intentionally NOT a signal model. It exists so ATLAS can collect
    forward outcomes when the strict directional setup is absent. The score is
    hard-capped below both the signal threshold and any execution path.
    """
    ks = atlas._spot_klines(symbol)
    if len(ks) < 100:
        return None
    closes = [x['close'] for x in ks]
    vols = [x['volume'] for x in ks]
    px = closes[-1]
    ema20 = atlas._ema(closes[-80:], 20)
    ema50 = atlas._ema(closes[-120:], 50)
    rsi = atlas._rsi(closes, 14)
    atr = atlas._atr(ks, 14)
    if not px or not ema20 or not ema50 or not atr or atr <= 0:
        return None

    vol_base = sum(vols[-21:-1]) / 20 if len(vols) >= 21 else vols[-1]
    rv = vols[-1] / vol_base if vol_base else 1.0
    rel = 50.0 if symbol == 'BTCUSDT' else atlas._cloud_relative(ks, btc_ks)
    mom24 = ((px / closes[-25]) - 1) * 100 if len(closes) >= 25 and closes[-25] else 0.0

    # Four transparent weak-direction votes. This labels a market state; it does
    # not claim tradeability and cannot become a signal candidate.
    votes = 0
    votes += 1 if px >= ema20 else -1
    votes += 1 if ema20 >= ema50 else -1
    votes += 1 if rsi >= 50 else -1
    votes += 1 if mom24 >= 0 else -1
    direction = 'LONG' if votes >= 0 else 'SHORT'

    ema_gap_pct = abs(ema20 / ema50 - 1) * 100 if ema50 else 0
    px_gap_pct = abs(px / ema20 - 1) * 100 if ema20 else 0
    strength = min(9.0,
                   abs(votes) * 1.25 +
                   min(2.0, abs(rsi - 50) * 0.12) +
                   min(2.0, ema_gap_pct * 2.0) +
                   min(1.5, px_gap_pct * 1.5) +
                   min(1.0, abs(mom24) * 0.15))
    research_score = round(min(59.0, 50.0 + strength), 2)

    sup, res, sd, rd = atlas._cloud_sr(ks)
    return {
        'symbol': symbol,
        'direction': direction,
        'entry': px,
        'champion_score': research_score,
        'champion_take': False,
        'challenger_take': False,
        'final_score': research_score,
        'opportunity_score': research_score,
        'execution_decision': 'RESEARCH_OBSERVATION_ONLY',
        'trade_plan_status': 'RESEARCH_ONLY',
        'rr_tp1': None,
        'rr_tp2': None,
        'futures_available': False,
        'futures_provider': None,
        'futures_score': None,
        'liquidity_score': None,
        'volume_quality': round(max(0, min(100, 45 + (rv - 1) * 35)), 2),
        'relative_volume': round(rv, 3),
        'relative_strength_score': round(rel, 2),
        'regime': 'NEUTRAL_RESEARCH',
        'support_strength': 60,
        'support_distance_pct': round(sd, 3) if sd is not None else None,
        'resistance_strength': 60,
        'resistance_distance_pct': round(rd, 3) if rd is not None else None,
        'playbook_primary': 'SHADOW_DIRECTIONAL_PROXY',
        'playbook_score': research_score,
        'playbook_all': ['SHADOW_DIRECTIONAL_PROXY'],
        'research_direction_votes': votes,
        'research_rsi14': round(rsi, 2),
        'research_momentum_24h_pct': round(mom24, 3),
        'research_sampling_lane': True,
        'auto_source': 'CLOUD_FORWARD_SHADOW_DIRECTION_RESEARCH',
        'dedup_minutes': 50,
    }


def research_cloud_forward_cycle():
    """Collect forward evidence without weakening any signal/alert threshold."""
    state = atlas.CLOUD_FORWARD_STATE
    state['running'] = True
    state['last_started_at'] = atlas.now_iso()
    state['last_error'] = None
    state['last_failed_stage'] = None
    all_scored = []
    signal_candidates = []
    shadow_count = 0
    try:
        try:
            atlas.update_forward_returns()
        except Exception as exc:
            state['errors'] += 1
            state['last_error'] = f'forward_returns: {exc}'

        state['last_failed_stage'] = 'spot_btc'
        btc = atlas._spot_klines('BTCUSDT')

        state['last_failed_stage'] = 'score_universe'
        for symbol in atlas.ON_DEMAND_SYMBOLS:
            try:
                row = atlas.cloud_score_symbol(symbol, btc)
                if row is None:
                    row = shadow_research_score_symbol(symbol, btc)
                    if row is not None:
                        shadow_count += 1
                if not row:
                    continue
                all_scored.append(row)
                # Shadow proxies are structurally excluded from the signal lane,
                # regardless of numeric score. Strict production signal logic is unchanged.
                if (row.get('playbook_primary') != 'SHADOW_DIRECTIONAL_PROXY'
                        and row['final_score'] >= atlas.CLOUD_FORWARD_MIN_SCORE):
                    signal_candidates.append(row)
            except Exception as exc:
                state['errors'] += 1
                state['last_error'] = f'{symbol}: {exc}'

        all_scored.sort(key=lambda x: x['final_score'], reverse=True)
        signal_candidates.sort(key=lambda x: x['final_score'], reverse=True)
        signal_chosen = signal_candidates[:atlas.CLOUD_FORWARD_MAX_PER_CYCLE]

        signal_keys = {(x['symbol'], x['direction']) for x in signal_chosen}
        research_pool = [
            x for x in all_scored
            if x['final_score'] >= RESEARCH_SAMPLE_MIN_SCORE
            and (x['symbol'], x['direction']) not in signal_keys
        ]
        research_chosen = research_pool[:RESEARCH_SAMPLE_MAX_PER_CYCLE]

        state['last_failed_stage'] = 'store_signal_candidates'
        for row in signal_chosen:
            try:
                result = atlas.forward_observe(row)
                if isinstance(result, dict) and result.get('stored') is False:
                    state['deduped'] += 1
                else:
                    state['stored'] += 1
                try:
                    atlas.evaluate_confirmed_opportunity(row, True, 'CLOUD_FORWARD_ALPHA25_HARDENED')
                except Exception as alert_exc:
                    state['last_error'] = f'Alert engine: {alert_exc}'
            except Exception as exc:
                state['errors'] += 1
                state['last_error'] = str(exc)

        state['last_failed_stage'] = 'store_research_samples'
        selected_summary = []
        for row in research_chosen:
            sample = dict(row)
            sample['auto_source'] = sample.get('auto_source') or 'CLOUD_FORWARD_RESEARCH_SAMPLE'
            sample['execution_decision'] = 'RESEARCH_OBSERVATION_ONLY'
            sample['research_sampling_lane'] = True
            sample['champion_take'] = False
            sample['challenger_take'] = False
            sample['signal_threshold_at_entry'] = atlas.CLOUD_FORWARD_MIN_SCORE
            sample['research_threshold_at_entry'] = RESEARCH_SAMPLE_MIN_SCORE
            try:
                result = atlas.forward_observe(sample)
                if isinstance(result, dict) and result.get('stored') is False:
                    RESEARCH_LANE_STATE['research_deduped'] += 1
                else:
                    RESEARCH_LANE_STATE['research_stored'] += 1
                RESEARCH_LANE_STATE['research_selected'] += 1
                selected_summary.append({
                    'symbol': sample['symbol'],
                    'direction': sample['direction'],
                    'score': sample['final_score'],
                    'signal_qualified': False,
                    'research_method': sample.get('playbook_primary'),
                })
            except Exception as exc:
                RESEARCH_LANE_STATE['last_error'] = f'{row.get("symbol")}: {exc}'

        state['last_candidates'] = [
            {'symbol': x['symbol'], 'direction': x['direction'], 'score': x['final_score'], 'playbook': x.get('playbook_primary')}
            for x in signal_chosen
        ]
        state['cycles'] += 1
        state['last_success_at'] = atlas.now_iso()
        state['last_failed_stage'] = None

        RESEARCH_LANE_STATE['cycles'] += 1
        RESEARCH_LANE_STATE['scored_directional'] += len(all_scored)
        RESEARCH_LANE_STATE['shadow_directional_proxies'] += shadow_count
        RESEARCH_LANE_STATE['signal_qualified'] += len(signal_candidates)
        RESEARCH_LANE_STATE['last_top_scores'] = [
            {'symbol': x['symbol'], 'direction': x['direction'], 'score': x['final_score'], 'method': x.get('playbook_primary')}
            for x in all_scored[:7]
        ]
        RESEARCH_LANE_STATE['last_selected'] = selected_summary
        RESEARCH_LANE_STATE['last_success_at'] = atlas.now_iso()

        try:
            atlas.stage_expansion_report(24, True)
        except Exception as exc:
            state['last_error'] = f'Stage engine: {exc}'
    except Exception as exc:
        state['errors'] += 1
        state['last_error'] = str(exc)
        RESEARCH_LANE_STATE['last_error'] = str(exc)
    finally:
        state['running'] = False
        state['last_finished_at'] = atlas.now_iso()
    return dict(state)


atlas.cloud_forward_cycle = research_cloud_forward_cycle


if __name__ == '__main__':
    os.chdir(atlas.ROOT)
    port = int(os.environ.get('PORT', '8080'))
    server = runtime.AtlasHTTPServer(('0.0.0.0', port), runtime.RuntimeHandler)

    for name, target in (
        ('smart_money', atlas.auto_loop),
        ('news', atlas.news_loop),
        ('cloud_forward', atlas.cloud_forward_loop),
    ):
        threading.Thread(target=runtime._supervise, args=(name, target), daemon=True, name=f'atlas-{name}').start()

    print('ATLAS V7 research-sampling production runtime', flush=True)
    print(f'Boot ID: {runtime.BOOT_ID}', flush=True)
    print(f'Data: {atlas.DATA}', flush=True)
    print('Signal gate unchanged; neutral states use non-executable shadow direction research', flush=True)
    print(f'Research sample threshold: {RESEARCH_SAMPLE_MIN_SCORE}', flush=True)
    print(f'Listening on port {port}', flush=True)
    server.serve_forever(poll_interval=0.25)
