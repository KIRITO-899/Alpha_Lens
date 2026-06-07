import unittest

from signals import ripple_engine as re


class TestNormalizeTicker(unittest.TestCase):
    def test_strips_ns_bo_and_uppercases(self):
        self.assertEqual(re.normalize_ticker('tcs'), 'TCS')
        self.assertEqual(re.normalize_ticker('TCS.NS'), 'TCS')
        self.assertEqual(re.normalize_ticker('infy.bo'), 'INFY')
        self.assertEqual(re.normalize_ticker('  ongc.ns  '), 'ONGC')


class TestDirectionFlipsWithSign(unittest.TestCase):
    def test_oil_up_is_bullish_upstream_bearish_omc(self):
        r = re.compute_ripple('brent', 5.0, 'MAJOR')
        by = {n['ticker']: n for n in r['direct']}
        self.assertEqual(by['ONGC.NS']['direction'], 'BULLISH')   # upstream
        self.assertEqual(by['BPCL.NS']['direction'], 'BEARISH')   # OMC

    def test_oil_down_flips_every_direction(self):
        up = re.compute_ripple('brent', 5.0, 'MAJOR')
        dn = re.compute_ripple('brent', -5.0, 'MAJOR')
        up_by = {n['ticker']: n['direction'] for n in up['direct']}
        dn_by = {n['ticker']: n['direction'] for n in dn['direct']}
        for t in up_by:
            self.assertNotEqual(up_by[t], dn_by[t], f'{t} should flip on sign flip')


class TestExpectedMoveScalingAndCap(unittest.TestCase):
    def test_move_scales_linearly_with_beta(self):
        r = re.compute_ripple('brent', 2.0, 'SIGNIFICANT')
        ongc = next(n for n in r['direct'] if n['ticker'] == 'ONGC.NS')
        # beta +0.85 * 2.0 = 1.70
        self.assertAlmostEqual(ongc['expected_move_pct'], 1.70, places=2)

    def test_extreme_move_is_capped(self):
        r = re.compute_ripple('vix_in', 60.0, 'MAJOR')  # huge vol spike
        for n in r['direct'] + r['second_order']:
            self.assertLessEqual(abs(n['expected_move_pct']), re.MAX_EXPECTED_MOVE)


class TestConfidenceDecay(unittest.TestCase):
    def test_direct_outranks_second_order(self):
        r = re.compute_ripple('brent', 5.0, 'MAJOR')
        min_direct = min(n['confidence'] for n in r['direct'])
        max_second = max(n['confidence'] for n in r['second_order'])
        self.assertGreaterEqual(min_direct, max_second)

    def test_confidence_within_bounds(self):
        r = re.compute_ripple('copper', 4.0, 'MAJOR')
        for n in r['direct'] + r['second_order']:
            self.assertGreaterEqual(n['confidence'], re.CONF_FLOOR)
            self.assertLessEqual(n['confidence'], re.CONF_CEIL)


class TestSectorRollup(unittest.TestCase):
    def test_sectors_sorted_by_abs_net(self):
        r = re.compute_ripple('brent', 5.0, 'MAJOR')
        nets = [abs(s['net_move_pct']) for s in r['sector']]
        self.assertEqual(nets, sorted(nets, reverse=True))

    def test_sector_direction_matches_net_sign(self):
        r = re.compute_ripple('brent', 5.0, 'MAJOR')
        for s in r['sector']:
            if s['net_move_pct'] > 0:
                self.assertEqual(s['direction'], 'BULLISH')
            elif s['net_move_pct'] < 0:
                self.assertEqual(s['direction'], 'BEARISH')


class TestPortfolioImpact(unittest.TestCase):
    def test_no_watchlist_is_not_applicable(self):
        r = re.compute_ripple('brent', 5.0, 'MAJOR')
        self.assertFalse(r['portfolio']['applicable'])

    def test_watchlist_matches_regardless_of_suffix(self):
        r = re.compute_ripple('brent', 5.0, 'MAJOR', watchlist=['ongc', 'INDIGO.NS', 'TCS'])
        p = r['portfolio']
        self.assertTrue(p['applicable'])
        self.assertEqual(p['total'], 3)
        # ONGC + INDIGO are in the oil graph; TCS is not.
        self.assertEqual(p['exposure_count'], 2)
        hit_tickers = {re.normalize_ticker(h['ticker']) for h in p['hits']}
        self.assertEqual(hit_tickers, {'ONGC', 'INDIGO'})

    def test_no_exposure_when_none_match(self):
        r = re.compute_ripple('brent', 5.0, 'MAJOR', watchlist=['TCS', 'WIPRO'])
        self.assertTrue(r['portfolio']['applicable'])
        self.assertEqual(r['portfolio']['exposure_count'], 0)


class TestActionWindow(unittest.TestCase):
    def test_closed_market_is_actionable(self):
        r = re.compute_ripple('brent', 5.0, 'MAJOR', during_nse_hours=0)
        self.assertEqual(r['action_window']['state'], 'ACTIONABLE')

    def test_open_market_is_live(self):
        r = re.compute_ripple('brent', 5.0, 'MAJOR', during_nse_hours=1)
        self.assertEqual(r['action_window']['state'], 'LIVE')

    def test_urgency_tracks_shock_level(self):
        self.assertEqual(
            re.compute_ripple('brent', 5.0, 'MAJOR')['action_window']['urgency'], 'HIGH')
        self.assertEqual(
            re.compute_ripple('brent', 3.0, 'SIGNIFICANT')['action_window']['urgency'], 'MEDIUM')


class TestSafety(unittest.TestCase):
    def test_unknown_instrument_returns_valid_shell(self):
        r = re.compute_ripple('dogecoin', 9.0, 'MAJOR', watchlist=['TCS'])
        self.assertEqual(r['direct'], [])
        self.assertEqual(r['second_order'], [])
        self.assertEqual(r['sector'], [])
        self.assertIn('action_window', r)

    def test_zero_move_returns_shell(self):
        r = re.compute_ripple('brent', 0.0, None)
        self.assertEqual(r['direct'], [])

    def test_bad_pct_does_not_raise(self):
        r = re.compute_ripple('brent', None, 'MAJOR')
        self.assertEqual(r['pct'], 0.0)


if __name__ == '__main__':
    unittest.main()
