import unittest

from consensus_tiebreak_shadow import build_shadow_from_decision


def decision(lv=2, sv=2, momentum=-1.25, wait=True):
    return {
        'ok':True,'symbol':'BTCUSDT','entry':80000,
        'decision':'WAIT' if wait else 'LONG',
        'actionable_decision':'WAIT' if wait else 'LONG',
        'wait_reason':'NO_DIRECTIONAL_CONSENSUS' if wait else None,
        'score':None if wait else 70,'signal_threshold':68,
        'direction_votes_long':lv,'direction_votes_short':sv,
        'indicators':{'momentum_24h_pct':momentum},
        'generated_at':'2026-08-28T08:00:00+00:00',
    }


class ConsensusTiebreakShadowTests(unittest.TestCase):
    def test_exact_two_two_negative_momentum_is_short_shadow(self):
        x=build_shadow_from_decision(decision(momentum=-1.25))
        self.assertEqual(x['status'],'SHADOW_SIGNAL')
        self.assertEqual(x['direction'],'SHORT')
        self.assertEqual(x['horizons_hours'],[1,3])
        self.assertTrue(x['shadow_only'])
        self.assertFalse(x['can_override_production'])
        self.assertFalse(x['can_execute'])
        self.assertEqual(x['production_threshold'],68.0)

    def test_exact_two_two_positive_momentum_is_long_shadow(self):
        x=build_shadow_from_decision(decision(momentum=2.0))
        self.assertEqual(x['status'],'SHADOW_SIGNAL')
        self.assertEqual(x['direction'],'LONG')

    def test_three_one_is_inactive(self):
        x=build_shadow_from_decision(decision(lv=3,sv=1,momentum=2.0))
        self.assertEqual(x['status'],'INACTIVE')
        self.assertEqual(x['reason'],'NOT_EXACT_2_2_TIE')

    def test_non_wait_production_is_never_shadow_override(self):
        x=build_shadow_from_decision(decision(wait=False,momentum=2.0))
        self.assertEqual(x['status'],'INACTIVE')
        self.assertEqual(x['reason'],'PRODUCTION_NOT_NO_CONSENSUS_WAIT')
        self.assertFalse(x['can_override_production'])


if __name__=='__main__':
    unittest.main()
