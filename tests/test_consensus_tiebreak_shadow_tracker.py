import unittest

from consensus_tiebreak_shadow_tracker import build_report


def sig(status='INACTIVE',direction=None,price=100,mom=-1,when='2026-08-28T08:00:00+00:00'):
    return {
        'ok':True,'status':status,'direction':direction,'reference_price':price,
        'momentum_24h_pct':mom,'generated_at':when,
        'source':'CONSENSUS_TIEBREAK_SHADOW_V1_MOMENTUM_1H_3H',
        'rule':'EXACT_2_2_FOLLOW_24H_MOMENTUM_SIGN',
        'shadow_only':True,'can_override_production':False,
    }


class ConsensusShadowTrackerTests(unittest.TestCase):
    def test_settles_short_at_one_and_three_hours(self):
        snaps=[
            {'captured_at':'2026-08-28T08:00:00+00:00','signals':{'BTCUSDT':sig('SHADOW_SIGNAL','SHORT',100,-1)}},
            {'captured_at':'2026-08-28T09:00:00+00:00','signals':{'BTCUSDT':sig(price=98,when='2026-08-28T09:00:00+00:00')}},
            {'captured_at':'2026-08-28T11:00:00+00:00','signals':{'BTCUSDT':sig(price=95,when='2026-08-28T11:00:00+00:00')}},
        ]
        r=build_report(snaps)
        self.assertEqual(r['coverage']['shadow_signal_episodes'],1)
        self.assertEqual(r['coverage']['settled_1h'],1)
        self.assertEqual(r['coverage']['settled_3h'],1)
        self.assertAlmostEqual(r['performance']['1h']['mean_directional_return_pct'],2.0,places=4)
        self.assertAlmostEqual(r['performance']['3h']['mean_directional_return_pct'],5.0,places=4)
        self.assertFalse(r['guardrails']['production_changed'])
        self.assertFalse(r['guardrails']['auto_promotion'])

    def test_deduplicates_repeated_signal_same_symbol_hour(self):
        snaps=[
            {'captured_at':'2026-08-28T08:05:00+00:00','signals':{'ETHUSDT':sig('SHADOW_SIGNAL','LONG',100,1,'2026-08-28T08:05:00+00:00')}},
            {'captured_at':'2026-08-28T08:40:00+00:00','signals':{'ETHUSDT':sig('SHADOW_SIGNAL','LONG',101,1,'2026-08-28T08:40:00+00:00')}},
        ]
        r=build_report(snaps)
        self.assertEqual(r['coverage']['shadow_signal_episodes'],1)

    def test_sampling_gap_over_75_minutes_does_not_fake_horizon(self):
        snaps=[
            {'captured_at':'2026-08-28T08:00:00+00:00','signals':{'SOLUSDT':sig('SHADOW_SIGNAL','LONG',100,1)}},
            {'captured_at':'2026-08-28T10:30:00+00:00','signals':{'SOLUSDT':sig(price=110,when='2026-08-28T10:30:00+00:00')}},
        ]
        r=build_report(snaps)
        self.assertEqual(r['coverage']['settled_1h'],0)


if __name__=='__main__':
    unittest.main()
