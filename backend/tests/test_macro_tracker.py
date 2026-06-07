import unittest

from marketdata.macro_tracker import (
    daily_returns, compute_vol_stats, MacroDataTracker as MT,
)


class TestDailyReturns(unittest.TestCase):
    def _almost(self, got, expected):
        self.assertEqual(len(got), len(expected))
        for g, e in zip(got, expected):
            self.assertAlmostEqual(g, e, places=6)

    def test_basic(self):
        # 100 -> 110 -> 99 : +10%, -10%
        self._almost(daily_returns([100, 110, 99]), [10.0, -10.0])

    def test_skips_none_and_zero_prev(self):
        # None tolerated; a zero close can't seed a return
        self._almost(daily_returns([None, 100, None, 105]), [5.0])
        self.assertEqual(daily_returns([0, 100]), [])  # prev=0 -> skipped

    def test_empty(self):
        self.assertEqual(daily_returns([]), [])
        self.assertEqual(daily_returns(None), [])


class TestComputeVolStats(unittest.TestCase):
    def test_known_values(self):
        r = compute_vol_stats([1, -1, 1, -1, 1], 3.0)
        self.assertEqual(r['sample'], 5)
        self.assertAlmostEqual(r['vol_pct'], 1.0954, places=3)
        self.assertEqual(r['sigma'], 2.74)        # 3.0 / 1.0954
        self.assertEqual(r['pctile'], 100.0)      # |3| >= all |returns|

    def test_sign_is_preserved(self):
        self.assertLess(compute_vol_stats([1, -1, 1, -1, 1], -3.0)['sigma'], 0)

    def test_insufficient_sample(self):
        r = compute_vol_stats([1, 2], 5.0)
        self.assertIsNone(r['sigma'])
        self.assertEqual(r['sample'], 2)

    def test_zero_vol(self):
        r = compute_vol_stats([0, 0, 0, 0, 0, 0], 1.0)
        self.assertIsNone(r['sigma'])

    def test_window_limits_sample(self):
        r = compute_vol_stats(list(range(-50, 51)), 2.0, window=20)
        self.assertEqual(r['sample'], 20)


class TestClassifyShockSigma(unittest.TestCase):
    def test_major_and_significant(self):
        self.assertEqual(MT.classify_shock({'change_pct_1d': 4.0, 'sigma': 3.6})[0], 'MAJOR')
        self.assertEqual(MT.classify_shock({'change_pct_1d': 2.0, 'sigma': 2.7})[0], 'SIGNIFICANT')

    def test_below_sigma_is_none(self):
        self.assertIsNone(MT.classify_shock({'change_pct_1d': 1.0, 'sigma': 1.0})[0])

    def test_abs_floor_suppresses_low_vol_noise(self):
        # statistically huge but economically trivial (< ABS_FLOOR_PCT)
        self.assertIsNone(MT.classify_shock({'change_pct_1d': 0.05, 'sigma': 9.0})[0])

    def test_negative_sigma_uses_magnitude(self):
        self.assertEqual(MT.classify_shock({'change_pct_1d': -4.0, 'sigma': -3.7})[0], 'MAJOR')


class TestClassifyShockFallback(unittest.TestCase):
    def test_falls_back_to_fixed_pct_when_no_sigma(self):
        self.assertEqual(MT.classify_shock({'change_pct_1d': 6.0, 'sigma': None, 'key': 'brent'})[0], 'MAJOR')
        self.assertEqual(MT.classify_shock({'change_pct_1d': 3.5, 'sigma': None, 'key': 'brent'})[0], 'SIGNIFICANT')
        self.assertIsNone(MT.classify_shock({'change_pct_1d': 1.0, 'sigma': None, 'key': 'brent'})[0])

    def test_unknown_key_no_sigma_is_none(self):
        self.assertIsNone(MT.classify_shock({'change_pct_1d': 9.0, 'sigma': None, 'key': 'dogecoin'})[0])

    def test_missing_move_is_none(self):
        self.assertIsNone(MT.classify_shock({})[0])


if __name__ == '__main__':
    unittest.main()
