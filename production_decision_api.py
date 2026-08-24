"""Single source of truth for the ATLAS browser decision card.

Exposes the same production cloud scorer used by the research runtime and
normalizes it into LONG / SHORT / WAIT with explicit WAIT diagnostics and
score attribution. Adds a research-only tactical 1-3h lane that can identify
short moves toward the next obstacle without weakening the production signal
threshold.
"""

VERSION = "PRODUCTION_DECISION_API_V3_TACTICAL"


def install(atlas):
    original_get = atlas.Handler.do_GET

    def build_decision(symbol):
        symbol = str(symbol or '').upper().replace('BINANCE:', '')
        if symbol not in atlas.ON_DEMAND_SYMBOLS:
            return {'ok': False, 'error': 'unsupported symbol', 'supported_symbols': list(atlas.ON_DEMAND_SYMBOLS), 'source': VERSION}

        btc = atlas._spot_klines('BTCUSDT')
        ks = btc if symbol == 'BTCUSDT' else atlas._spot_klines(symbol)
        if len(ks) < 100:
            return {'ok': False, 'error': 'insufficient candles', 'source': VERSION}

        closes = [x['close'] for x in ks]; vols = [x['volume'] for x in ks]; px = closes[-1]
        ema20 = atlas._ema(closes[-80:], 20); ema50 = atlas._ema(closes[-120:], 50)
        rsi = atlas._rsi(closes, 14); atr = atlas._atr(ks, 14)
        mom24 = ((px / closes[-25]) - 1) * 100 if len(closes) >= 25 and closes[-25] else 0.0
        long_votes = sum((px >= ema20, ema20 >= ema50, rsi >= 50, mom24 >= 0))
        short_votes = sum((px <= ema20, ema20 <= ema50, rsi <= 50, mom24 <= 0))
        vol_base = sum(vols[-21:-1]) / 20 if len(vols) >= 21 else vols[-1]
        rv = vols[-1] / vol_base if vol_base else 1.0
        sup, res, sd, rd = atlas._cloud_sr(ks)

        row = atlas.cloud_score_symbol(symbol, btc); threshold = float(atlas.CLOUD_FORWARD_MIN_SCORE)
        candidate_direction = row.get('direction') if isinstance(row, dict) else None
        score = atlas.fnum(row.get('final_score')) if isinstance(row, dict) else None
        qualified = bool(candidate_direction in ('LONG', 'SHORT') and score is not None and score >= threshold)
        decision = candidate_direction if qualified else 'WAIT'
        if row is None: reason = 'NO_DIRECTIONAL_CONSENSUS' if max(long_votes, short_votes) < 3 or long_votes == short_votes else 'SCORER_RETURNED_NO_CANDIDATE'
        elif not qualified: reason = 'SCORE_BELOW_SIGNAL_THRESHOLD'
        else: reason = 'SIGNAL_QUALIFIED'

        stop = target = rr = None
        if isinstance(row, dict):
            rr = atlas.fnum(row.get('rr_tp2'))
            if candidate_direction == 'LONG' and atr: stop, target = px - atr * 1.2, res
            elif candidate_direction == 'SHORT' and atr: stop, target = px + atr * 1.2, sup

        # Tactical lane: a separate 1-3h research opportunity. The nearby
        # obstacle becomes the destination/exit boundary, not automatically a
        # reason to discard the move. We still demand directional consensus,
        # positive room, a buffer before the level, and minimum tactical RR.
        tactical = {'status':'NO_SETUP','direction':None,'horizon':'1-3H','entry':px,'target':None,'stop_loss':None,'risk_reward':None,'room_to_obstacle_pct':None,'confidence':0,'reason':'NO_DIRECTIONAL_CONSENSUS','research_only':True}
        tdir = None
        if long_votes >= 3 and long_votes > short_votes: tdir = 'LONG'
        elif short_votes >= 3 and short_votes > long_votes: tdir = 'SHORT'
        if tdir and atr and atr > 0:
            obstacle_px = res if tdir == 'LONG' else sup
            if obstacle_px is not None:
                room = ((obstacle_px-px)/px*100) if tdir == 'LONG' else ((px-obstacle_px)/px*100)
                # Exit before the obstacle: reserve 15% of available room.
                usable = max(0.0, room * 0.85)
                target_px = px * (1 + usable/100) if tdir == 'LONG' else px * (1 - usable/100)
                # Tactical stop is tighter than swing stop.
                stop_px = px - atr*0.65 if tdir == 'LONG' else px + atr*0.65
                risk = abs(px-stop_px); reward = abs(target_px-px); trr = reward/risk if risk > 0 else None
                votes = long_votes if tdir == 'LONG' else short_votes
                momentum_aligned = (tdir == 'LONG' and mom24 >= 0) or (tdir == 'SHORT' and mom24 <= 0)
                confidence = 52 + (8 if votes == 4 else 3) + (6 if rv >= 0.8 else 0) + (4 if momentum_aligned else -4)
                if usable <= 0: status, treason = 'NO_SETUP','NO_ROOM_TO_OBSTACLE'
                elif trr is None or trr < 0.8: status, treason = 'WAIT','TACTICAL_RR_TOO_LOW'
                elif votes == 4 and trr >= 1.0: status, treason = f'{tdir}_TACTICAL','ROOM_TO_NEXT_OBSTACLE'
                elif votes >= 3 and trr >= 1.2: status, treason = f'{tdir}_TACTICAL','ROOM_TO_NEXT_OBSTACLE'
                else: status, treason = 'WATCH','NEEDS_CONFIRMATION'
                tactical = {'status':status,'direction':tdir,'horizon':'1-3H','entry':px,'target':round(target_px,10),'stop_loss':round(stop_px,10),'risk_reward':round(trr,3) if trr is not None else None,'room_to_obstacle_pct':round(room,3),'usable_room_pct':round(usable,3),'confidence':max(0,min(100,confidence)),'reason':treason,'exit_rule':'EXIT_BEFORE_NEXT_SUPPORT_RESISTANCE','research_only':True}

        return {
            'ok': True, 'source': VERSION, 'scoring_version': (row or {}).get('scoring_version') if isinstance(row, dict) else None,
            'symbol': symbol, 'decision': decision, 'candidate_direction': candidate_direction, 'signal_qualified': qualified,
            'wait_reason': None if qualified else reason, 'score': score, 'signal_threshold': threshold,
            'score_gap_to_signal': round(threshold-score,3) if score is not None and score < threshold else 0,
            'score_attribution': (row or {}).get('score_attribution') if isinstance(row, dict) else None,
            'entry': px, 'stop_loss': stop, 'take_profit': target, 'risk_reward': rr,
            'direction_votes': (row or {}).get('direction_votes') if isinstance(row, dict) else max(long_votes,short_votes),
            'direction_votes_long': (row or {}).get('direction_votes_long') if isinstance(row, dict) else long_votes,
            'direction_votes_short': (row or {}).get('direction_votes_short') if isinstance(row, dict) else short_votes,
            'execution_decision': (row or {}).get('execution_decision') if isinstance(row, dict) else None,
            'trade_plan_status': (row or {}).get('trade_plan_status') if isinstance(row, dict) else None,
            'playbook': (row or {}).get('playbook_primary') if isinstance(row, dict) else None,
            'futures_available': (row or {}).get('futures_available') if isinstance(row, dict) else None,
            'futures_provider': (row or {}).get('futures_provider') if isinstance(row, dict) else None,
            'futures_score': (row or {}).get('futures_score') if isinstance(row, dict) else None,
            'relative_strength_score': (row or {}).get('relative_strength_score') if isinstance(row, dict) else None,
            'volume_quality': (row or {}).get('volume_quality') if isinstance(row, dict) else None,
            'relative_volume': (row or {}).get('relative_volume') if isinstance(row, dict) else round(rv,3),
            'regime': (row or {}).get('regime') if isinstance(row, dict) else None,
            'tactical_opportunity': tactical,
            'timeframe_matrix': {'tactical_1_3h': tactical, 'swing': {'status':decision,'direction':candidate_direction,'score':score,'threshold':threshold,'risk_reward':rr}, 'macro': {'status':'CONTEXT_ONLY','note':'Daily/weekly independent scorer is the next lane; tactical does not override swing production safeguards.'}},
            'indicators': {'ema20':ema20,'ema50':ema50,'rsi14':rsi,'atr14':atr,'volume_ratio':rv,'momentum_24h_pct':mom24},
            'generated_at': atlas.now_iso(), 'research_only': True, 'live_execution': False,
        }

    atlas.production_decision = build_decision
    def do_GET(self):
        import urllib.parse
        u=urllib.parse.urlparse(self.path)
        if u.path == '/api/decision/current':
            q=urllib.parse.parse_qs(u.query); symbol=q.get('symbol',['BTCUSDT'])[0]
            try:
                result=build_decision(symbol); return self._json(result,200 if result.get('ok') else 400)
            except Exception as exc:
                return self._json({'ok':False,'error':f'{type(exc).__name__}: {exc}','source':VERSION,'research_only':True,'live_execution':False},500)
        return original_get(self)
    atlas.Handler.do_GET=do_GET
    return {'enabled':True,'version':VERSION,'endpoint':'/api/decision/current','tactical_lane':'1-3H_RESEARCH_ONLY'}
