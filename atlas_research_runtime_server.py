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


def research_cloud_forward_cycle():
    """Collect forward evidence without weakening any trading/signal threshold.

    The strict CLOUD_FORWARD_MIN_SCORE remains the signal lane. A separate
    research lane stores a few of the best directional setups below that gate
    so ATLAS can learn what *didn't* qualify as well as what did. Research-lane
    rows never generate alerts and never imply execution.
    """
    state = atlas.CLOUD_FORWARD_STATE
    state['running'] = True
    state['last_started_at'] = atlas.now_iso()
    state['last_error'] = None
    state['last_failed_stage'] = None
    all_scored = []
    signal_candidates = []
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
                if not row:
                    continue
                all_scored.append(row)
                if row['final_score'] >= atlas.CLOUD_FORWARD_MIN_SCORE:
                    signal_candidates.append(row)
            except Exception as exc:
                state['errors'] += 1
                state['last_error'] = f'{symbol}: {exc}'

        all_scored.sort(key=lambda x: x['final_score'], reverse=True)
        signal_candidates.sort(key=lambda x: x['final_score'], reverse=True)
        signal_chosen = signal_candidates[:atlas.CLOUD_FORWARD_MAX_PER_CYCLE]

        # Research lane: sample top directional states even when they are below
        # the strict signal threshold. Exclude rows already selected by signal lane.
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
            sample['auto_source'] = 'CLOUD_FORWARD_RESEARCH_SAMPLE'
            sample['execution_decision'] = 'RESEARCH_OBSERVATION_ONLY'
            sample['research_sampling_lane'] = True
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
        RESEARCH_LANE_STATE['signal_qualified'] += len(signal_candidates)
        RESEARCH_LANE_STATE['last_top_scores'] = [
            {'symbol': x['symbol'], 'direction': x['direction'], 'score': x['final_score']}
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


# Patch only the cloud-forward cycle. The base collector, signal thresholds,
# alert thresholds, Smart Money worker and HTTP handler remain unchanged.
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
    print('Signal gate unchanged; separate forward research lane enabled', flush=True)
    print(f'Research sample threshold: {RESEARCH_SAMPLE_MIN_SCORE}', flush=True)
    print(f'Listening on port {port}', flush=True)
    server.serve_forever(poll_interval=0.25)
