import unittest

from marketdata.price_resolver import simulate_exit, to_favorable_bars

# Defaults used across tests: stop=1.0%, target=2.0%, partial at +1R (=+1.0%),
# 50% booked at partial. R = stop = 1.0%.
S, T = 1.0, 2.0


def sim(bars, **kw):
    return simulate_exit(bars, S, T, **kw)


class TestTerminalOutcomes(unittest.TestCase):
    def test_clean_target_blended_1_5R(self):
        r = sim([(0, 2.5, -0.2, 2.4)])
        self.assertEqual(r['status'], 'Predicted Target Hit')
        self.assertAlmostEqual(r['pnl_pct'], 1.5)   # 0.5*1R + 0.5*2R

    def test_stop_before_partial_is_full_loss(self):
        r = sim([(0, 0.5, -1.2, -1.1)])
        self.assertEqual(r['status'], 'Stop Loss Hit')
        self.assertAlmostEqual(r['pnl_pct'], -1.0)

    def test_partial_then_breakeven_is_a_WIN(self):
        # The core win-rate lever: hit +1R, reverse fully → +0.5R booked, not a loss.
        r = sim([(0, 1.2, -0.3, 1.1), (1.0, 1.0, -0.5, -0.4)])
        self.assertEqual(r['status'], 'Breakeven Exit')
        self.assertAlmostEqual(r['pnl_pct'], 0.5)
        self.assertGreater(r['pnl_pct'], 0)

    def test_partial_then_target(self):
        r = sim([(0, 1.2, -0.3, 1.1), (1.0, 2.5, 0.8, 2.4)])
        self.assertEqual(r['status'], 'Predicted Target Hit')
        self.assertAlmostEqual(r['pnl_pct'], 1.5)


class TestAmbiguousBarTiebreak(unittest.TestCase):
    def test_both_touched_close_up_books_partial(self):
        r = sim([(0, 1.5, -1.1, 0.9)])      # close up → favorable first
        self.assertTrue(r['partial_done'])
        self.assertFalse(r['resolved'])     # runner deferred to next bar
        self.assertAlmostEqual(r['pnl_pct'], 0.5)

    def test_both_touched_close_down_is_stop(self):
        r = sim([(0, 1.5, -1.1, -0.9)])     # close down → stop first
        self.assertEqual(r['status'], 'Stop Loss Hit')
        self.assertAlmostEqual(r['pnl_pct'], -1.0)


class TestGapFills(unittest.TestCase):
    def test_gap_down_through_stop_fills_at_open(self):
        r = sim([(-1.5, -1.2, -2.0, -1.8)])
        self.assertEqual(r['status'], 'Stop Loss Hit')
        self.assertAlmostEqual(r['pnl_pct'], -1.5)   # worse than -1R, honest

    def test_gap_up_through_target_fills_at_open(self):
        r = sim([(2.3, 2.5, 2.1, 2.4)])
        self.assertEqual(r['status'], 'Predicted Target Hit')
        self.assertAlmostEqual(r['pnl_pct'], 2.3)    # whole position at the gap


class TestExpiry(unittest.TestCase):
    def test_expire_no_touch_books_drift(self):
        r = sim([(0, 0.5, -0.5, 0.2), (0.2, 0.6, -0.4, 0.1)], expire_close_pct=0.1)
        self.assertEqual(r['status'], 'Expired')
        self.assertAlmostEqual(r['pnl_pct'], 0.1)

    def test_expire_after_partial_keeps_locked_gain(self):
        r = sim([(0, 1.2, -0.3, 1.1)], expire_close_pct=0.3)
        self.assertEqual(r['status'], 'Expired')
        self.assertAlmostEqual(r['pnl_pct'], 0.5 * 1.0 + 0.5 * 0.3)  # 0.65

    def test_open_runner_unresolved_without_expiry(self):
        r = sim([(0, 1.2, -0.3, 1.1)])   # partial booked, no expire arg
        self.assertFalse(r['resolved'])
        self.assertTrue(r['partial_done'])
        self.assertAlmostEqual(r['remaining'], 0.5)


class TestPartialDisabledAndCost(unittest.TestCase):
    def test_partial_disabled_is_first_barrier_full_target(self):
        r = sim([(0, 2.5, -0.2, 2.4)], partial_enabled=False)
        self.assertEqual(r['status'], 'Predicted Target Hit')
        self.assertAlmostEqual(r['pnl_pct'], 2.0)   # full 2R, no partial booking

    def test_partial_disabled_both_touched_close_down_is_stop(self):
        # honest close-tiebreak even with partial off (no benefit-of-the-doubt)
        r = sim([(0, 2.2, -1.1, -0.9)], partial_enabled=False)
        self.assertEqual(r['status'], 'Stop Loss Hit')

    def test_cost_haircut_applied_once(self):
        r = sim([(0, 2.5, -0.2, 2.4)], cost_pct=0.2)
        self.assertAlmostEqual(r['pnl_pct'], 1.5 - 0.2)


class TestToFavorableBars(unittest.TestCase):
    def test_bullish_passthrough(self):
        out = to_favorable_bars([(100, 102, 99, 101)], 100, True)
        self.assertEqual(out, [(0.0, 2.0, -1.0, 1.0)])

    def test_bearish_flips_high_low_and_sign(self):
        out = to_favorable_bars([(100, 102, 99, 101)], 100, False)
        o, h, l, c = out[0]
        self.assertAlmostEqual(o, 0.0)
        self.assertAlmostEqual(h, 1.0)    # favorable high = -(price low%) = -(-1) = +1
        self.assertAlmostEqual(l, -2.0)   # favorable low  = -(price high%) = -(2)
        self.assertAlmostEqual(c, -1.0)   # price rose → unfavorable for a short

    def test_bearish_winning_path_resolves_target(self):
        # base 100, price falls to 97 (a 3% down move) → favorable +3% → target hit
        favbars = to_favorable_bars([(100, 100.2, 97.0, 97.5)], 100, False)
        r = simulate_exit(favbars, S, T)
        self.assertEqual(r['status'], 'Predicted Target Hit')
        self.assertGreater(r['pnl_pct'], 0)

    def test_bad_base_price_returns_empty(self):
        self.assertEqual(to_favorable_bars([(1, 2, 3, 4)], 0, True), [])


class TestSafety(unittest.TestCase):
    def test_empty_bars_unresolved(self):
        r = sim([])
        self.assertFalse(r['resolved'])
        self.assertIsNone(r['pnl_pct'])

    def test_none_fields_do_not_crash(self):
        r = sim([(None, None, None, None), (0, 2.5, -0.1, 2.4)])
        self.assertEqual(r['status'], 'Predicted Target Hit')

    def test_bad_inputs_safe(self):
        r = simulate_exit([(0, 1, -1, 0)], 'x', None)
        self.assertFalse(r['resolved'])


if __name__ == '__main__':
    unittest.main()
