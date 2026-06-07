import unittest

from signals.nifty_outlook import compute_nifty_outlook, DRIVERS, CONF_CEIL, CONF_FLOOR


def _snap(nifty=None, **drivers):
    """Build a snapshot: driver=change_pct_1d kwargs, plus optional nifty dict."""
    s = {k: {'change_pct_1d': v} for k, v in drivers.items()}
    if nifty is not None:
        s['nifty'] = nifty
    return s


class TestDirection(unittest.TestCase):
    def test_risk_off_is_bearish(self):
        # VIX +20, DXY +1, Brent +4 → all bearish for NIFTY
        o = compute_nifty_outlook(_snap(vix_us=20, dxy=1.0, brent=4.0,
                                        nifty={'last': 24000, 'vol_pct': 0.7}),
                                  during_nse_hours=0)
        self.assertLess(o['expected_move_pct'], 0)
        self.assertEqual(o['stance'], 'BEARISH')
        self.assertEqual(o['drivers'][0]['key'], 'vix_us')   # strongest cue
        self.assertEqual(o['nifty_last'], 24000)

    def test_risk_on_is_bullish(self):
        # VIX -15 (calm), Copper +3 (growth), rupee stronger (usdinr -0.4)
        o = compute_nifty_outlook(_snap(vix_us=-15, copper=3, usdinr=-0.4))
        self.assertGreater(o['expected_move_pct'], 0)
        self.assertIn(o['stance'], ('BULLISH', 'MILD_BULLISH'))

    def test_each_driver_sign(self):
        self.assertLess(compute_nifty_outlook(_snap(brent=5))['expected_move_pct'], 0)
        self.assertGreater(compute_nifty_outlook(_snap(copper=5))['expected_move_pct'], 0)
        self.assertLess(compute_nifty_outlook(_snap(dxy=1))['expected_move_pct'], 0)
        self.assertLess(compute_nifty_outlook(_snap(us10y=5))['expected_move_pct'], 0)
        self.assertLess(compute_nifty_outlook(_snap(usdinr=1))['expected_move_pct'], 0)


class TestMagnitudeAndRange(unittest.TestCase):
    def test_aggregation(self):
        # vix_us 20 → -0.9 ; dxy 1 → -0.40 ; brent 4 → -0.36 ; total -1.66
        o = compute_nifty_outlook(_snap(vix_us=20, dxy=1.0, brent=4.0))
        self.assertAlmostEqual(o['expected_move_pct'], -1.66, places=2)

    def test_single_contribution_cap(self):
        # vix_us 100 would be -4.5, capped at -1.2
        o = compute_nifty_outlook(_snap(vix_us=100))
        self.assertAlmostEqual(o['drivers'][0]['contribution_pct'], -1.2, places=2)

    def test_range_from_vol(self):
        o = compute_nifty_outlook(_snap(brent=3, nifty={'last': 100, 'vol_pct': 1.5}))
        self.assertAlmostEqual(o['expected_move_pct'], -0.27, places=2)
        self.assertAlmostEqual(o['range_low_pct'], -1.77, places=2)   # -0.27 - 1.5
        self.assertAlmostEqual(o['projected_level'], 99.73, places=2)

    def test_default_range_without_vol(self):
        o = compute_nifty_outlook(_snap(brent=3))
        self.assertAlmostEqual(o['range_high_pct'] - o['expected_move_pct'], 0.8, places=2)


class TestConfidence(unittest.TestCase):
    def test_capped(self):
        aligned = _snap(vix_us=30, dxy=1.5, us10y=8, brent=6, usdinr=1.0, gold=3)
        o = compute_nifty_outlook(aligned)
        self.assertLessEqual(o['confidence'], CONF_CEIL)
        self.assertGreaterEqual(o['confidence'], CONF_FLOOR)

    def test_conflict_lowers_agreement(self):
        # VIX up (bearish) vs Copper up (bullish) → cues disagree
        o = compute_nifty_outlook(_snap(vix_us=20, copper=10))
        self.assertLess(o['agreement'], 1.0)
        aligned = compute_nifty_outlook(_snap(vix_us=20, dxy=1.0))
        self.assertGreaterEqual(aligned['agreement'], o['agreement'])


class TestHorizonAndSafety(unittest.TestCase):
    def test_horizon_framing(self):
        self.assertEqual(compute_nifty_outlook(_snap(brent=3), during_nse_hours=0)['horizon'], 'Next session')
        self.assertEqual(compute_nifty_outlook(_snap(brent=3), during_nse_hours=1)['horizon'], 'Rest of session')

    def test_empty_inputs_safe(self):
        for arg in ({}, None, {'nifty': {'last': 24000}}):
            o = compute_nifty_outlook(arg)
            self.assertFalse(o['applicable'])
            self.assertEqual(o['expected_move_pct'], 0.0)
            self.assertEqual(o['drivers'], [])

    def test_non_driver_instruments_ignored(self):
        # wti/silver/natgas/banknifty are intentionally NOT NIFTY drivers
        o = compute_nifty_outlook(_snap(wti=10, silver=10, natgas=10, banknifty=10))
        self.assertFalse(o['applicable'])

    def test_driver_set_is_deduped(self):
        # no double-counting oil (wti) or precious (silver); 8 curated drivers
        self.assertEqual(set(DRIVERS), {
            'vix_us', 'dxy', 'us10y', 'brent', 'usdinr', 'gold', 'copper', 'vix_in'})


if __name__ == '__main__':
    unittest.main()
