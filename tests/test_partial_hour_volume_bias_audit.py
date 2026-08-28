import unittest

from partial_hour_volume_bias_audit import audit


class PartialHourVolumeBiasAuditTests(unittest.TestCase):
    def test_direct_volume_bonus_can_flip_wait_to_qualified(self):
        rows=[{
            'captured_at':'2026-08-20T10:15:00+00:00',
            'decisions':{
                'ETHUSDT':{
                    'ok':True,
                    'generated_at':'2026-08-20T10:15:00+00:00',
                    'scoring_version':'PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE',
                    'candidate_direction':'LONG','score':67,'signal_threshold':68,
                    'signal_qualified':False,'relative_volume':0.30,
                    'score_attribution':{'volume_bonus':0,'raw_score':67,'obstacle_adjustment':0,'obstacle_distance_pct':1.8},
                    'wait_reason':'SCORE_BELOW_SIGNAL_THRESHOLD',
                }
            }
        }]
        r=audit(rows)
        h=r['independent_hourly_observations']
        self.assertEqual(h['n'],1)
        self.assertEqual(h['old_waits'],1)
        self.assertEqual(h['direct_volume_flips'],1)
        self.assertEqual(h['qualification_flips'],1)
        self.assertEqual(h['direct_flip_rate_pct_among_old_waits'],100.0)
        ex=r['most_affected_hourly_examples'][0]
        self.assertAlmostEqual(ex['counterfactual_paced_relative_volume'],1.2,places=5)
        self.assertAlmostEqual(ex['direct_volume_score_delta'],2.0,places=5)
        self.assertEqual(ex['counterfactual_score'],69)

    def test_no_consensus_is_not_credited_to_volume(self):
        rows=[{
            'captured_at':'2026-08-20T10:15:00+00:00',
            'decisions':{
                'ETHUSDT':{
                    'ok':True,'generated_at':'2026-08-20T10:15:00+00:00',
                    'scoring_version':'PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE',
                    'candidate_direction':'LONG','score':65,'signal_threshold':68,
                    'signal_qualified':False,'relative_volume':0.2,
                    'score_attribution':{'volume_bonus':0,'raw_score':65},
                    'wait_reason':'SCORE_BELOW_SIGNAL_THRESHOLD',
                },
                'BTCUSDT':{
                    'ok':True,'generated_at':'2026-08-20T10:15:10+00:00',
                    'scoring_version':None,'score':None,'relative_volume':0.1,
                    'wait_reason':'NO_DIRECTIONAL_CONSENSUS',
                }
            }
        },{
            'captured_at':'2026-08-20T10:16:00+00:00',
            'decisions':{
                'ETHUSDT':{
                    'ok':True,'generated_at':'2026-08-20T10:16:00+00:00',
                    'scoring_version':'PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE',
                    'candidate_direction':'LONG','score':65,'signal_threshold':68,
                    'signal_qualified':False,'relative_volume':0.2,
                    'score_attribution':{'volume_bonus':0,'raw_score':65},
                    'wait_reason':'SCORE_BELOW_SIGNAL_THRESHOLD',
                }
            }
        }]
        r=audit(rows)
        w=r['wait_attribution']
        self.assertEqual(w['no_directional_consensus_raw_observations'],1)
        self.assertEqual(w['no_directional_consensus_unique_symbol_hours'],1)
        # Repeated ETH observations in same hour collapse to one hourly behavior unit.
        self.assertEqual(r['independent_hourly_observations']['n'],1)

    def test_exact_breakout_recovery_adds_clear_space_delta(self):
        rows=[{
            'captured_at':'2026-08-20T10:30:00+00:00',
            'decisions':{
                'SOLUSDT':{
                    'ok':True,'generated_at':'2026-08-20T10:30:00+00:00',
                    'scoring_version':'PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE',
                    'candidate_direction':'LONG','direction_votes':4,'momentum_24h_pct':1.2,
                    'score':65,'signal_threshold':68,'signal_qualified':False,'relative_volume':0.4,
                    'breakout_context':{'confirmed':False,'beyond_prior_24h_range':True,'current_body_atr':0.2},
                    'score_attribution':{'volume_bonus':0,'raw_score':65,'obstacle_adjustment':0,'obstacle_distance_pct':None},
                    'wait_reason':'SCORE_BELOW_SIGNAL_THRESHOLD',
                }
            }
        }]
        r=audit(rows)
        h=r['independent_hourly_observations']
        self.assertEqual(h['breakout_context_available'],1)
        self.assertEqual(h['breakout_context_coverage_pct'],100.0)
        ex=r['most_affected_hourly_examples'][0]
        self.assertTrue(ex['breakout_recovered'])
        self.assertEqual(ex['breakout_obstacle_score_delta'],3.0)
        self.assertEqual(ex['counterfactual_score'],68)
        self.assertTrue(ex['qualification_flip'])


if __name__=='__main__':
    unittest.main()
