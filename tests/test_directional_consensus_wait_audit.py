import unittest

from directional_consensus_wait_audit import audit, de_duplicate, vote_state


def rec(symbol, when, price=105, ema20=100, ema50=110, rsi=55, mom=-2, change3=1.0):
    return {
        'symbol':symbol,'wait_at':when,'wait_price':price,
        'candidate_direction':'NONE','score':None,'threshold':68,
        'reason':'NO_DIRECTIONAL_CONSENSUS',
        'decision_context':{
            'direction_votes_long':2,'direction_votes_short':2,
            'ema20':ema20,'ema50':ema50,'rsi14':rsi,'momentum_24h_pct':mom,
        },
        'horizons':{
            '1h':{'change_pct':change3/3,'max_up_pct':max(change3/3,0),'max_down_pct':min(change3/3,0)},
            '3h':{'change_pct':change3,'max_up_pct':max(change3,0),'max_down_pct':min(change3,0)},
            '12h':{'change_pct':change3*2,'max_up_pct':max(change3*2,0),'max_down_pct':min(change3*2,0)},
            '24h':{'change_pct':change3*2.5,'max_up_pct':max(change3*2.5,0),'max_down_pct':min(change3*2.5,0)},
        }
    }


class DirectionalConsensusWaitAuditTests(unittest.TestCase):
    def test_vote_rebuild_exact_two_two_and_fixed_sides(self):
        r=rec('BTCUSDT','2026-08-20T10:05:00+00:00')
        v=vote_state(r)
        # price > EMA20 = LONG, EMA20 < EMA50 = SHORT,
        # RSI > 50 = LONG, momentum < 0 = SHORT => 2-2.
        self.assertEqual(v['long_votes_rebuilt'],2)
        self.assertEqual(v['short_votes_rebuilt'],2)
        self.assertEqual(v['trend_side'],'SHORT')
        self.assertEqual(v['momentum_side'],'SHORT')
        self.assertEqual(v['pattern'],'PL-TS-RL-MS')

    def test_same_symbol_hour_is_deduplicated_to_earliest(self):
        a=rec('ETHUSDT','2026-08-20T10:05:00+00:00')
        b=rec('ETHUSDT','2026-08-20T10:45:00+00:00')
        c=rec('ETHUSDT','2026-08-20T11:05:00+00:00')
        out=de_duplicate([b,c,a])
        self.assertEqual(len(out),2)
        self.assertEqual(out[0]['wait_at'],a['wait_at'])

    def test_audit_keeps_production_unchanged_and_measures_rules(self):
        rows=[]
        symbols=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT']
        for i,s in enumerate(symbols):
            # Built vote state remains 2-2. Negative market return makes the
            # predefined SHORT trend/momentum side profitable.
            rows.append(rec(s,f'2026-08-{20+i:02d}T10:05:00+00:00',change3=-1.0))
        report=audit({'schema':'TEST_WAIT_OUTCOMES','records':rows})
        self.assertEqual(report['coverage']['exact_2_2_episodes'],6)
        self.assertFalse(report['guardrails']['production_changed'])
        self.assertEqual(report['guardrails']['production_threshold'],68)
        self.assertGreater(report['fixed_tie_breakers']['trend_side']['3h']['mean_directional_return_pct'],0)
        self.assertGreater(report['fixed_tie_breakers']['momentum_side']['3h']['mean_directional_return_pct'],0)
        self.assertEqual(report['wait_baseline_market_movement']['3h']['terminal_move_ge_1_pct'],6)


if __name__=='__main__':
    unittest.main()
