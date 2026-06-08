"""Unit tests for marketdata.price_resolver — the pure price/ATR rules.

These lock in the two fixes:
  * select_fresh_close: kills the "stale close" bug (daily series lags a session
    while regularMarketPrice already holds the genuine latest close).
  * atr_stop_target: stop = ATR/2, target = ATR, with a flat 1%/2% fallback.
"""
import unittest
from datetime import datetime, date, timezone, timedelta

from marketdata.price_resolver import select_fresh_close, atr_stop_target

IST = timezone(timedelta(hours=5, minutes=30))


def _ist(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=IST)


class TestSelectFreshClose(unittest.TestCase):
    # The live IOC case: daily series ends Fri 138.26, regularMarketPrice carries
    # Mon's real close 135.6 stamped at 15:30 -> must use 135.6, prev 138.26.
    IOC_DAILY = [
        (date(2026, 6, 2), 138.83),
        (date(2026, 6, 3), 137.38),
        (date(2026, 6, 4), 138.95),
        (date(2026, 6, 5), 138.26),
    ]

    def test_fresh_regular_price_beats_stale_daily(self):
        last, prev = select_fresh_close(self.IOC_DAILY, 135.6, _ist(2026, 6, 8, 15, 30))
        self.assertEqual(last, 135.6)
        self.assertEqual(prev, 138.26)

    def test_mid_session_reg_time_ignored(self):
        # reg_time before 15:30 => not a completed close => fall back to daily bar.
        last, prev = select_fresh_close(self.IOC_DAILY, 135.6, _ist(2026, 6, 8, 11, 0))
        self.assertEqual(last, 138.26)
        self.assertEqual(prev, 138.95)

    def test_no_meta_uses_daily(self):
        last, prev = select_fresh_close(self.IOC_DAILY, None, None)
        self.assertEqual(last, 138.26)
        self.assertEqual(prev, 138.95)

    def test_stale_regular_price_older_than_daily_ignored(self):
        # reg_time older than the newest daily bar => ignore reg_price.
        last, prev = select_fresh_close(self.IOC_DAILY, 999.0, _ist(2026, 6, 1, 15, 30))
        self.assertEqual(last, 138.26)
        self.assertEqual(prev, 138.95)

    def test_reg_price_same_day_as_last_daily_bar(self):
        # daily already has today's bar AND reg_price matches the same day:
        # previous close must be the *prior* daily bar, not today's.
        daily = self.IOC_DAILY + [(date(2026, 6, 8), 135.6)]
        last, prev = select_fresh_close(daily, 135.6, _ist(2026, 6, 8, 15, 30))
        self.assertEqual(last, 135.6)
        self.assertEqual(prev, 138.26)

    def test_only_regular_price_no_daily(self):
        last, prev = select_fresh_close([], 135.6, _ist(2026, 6, 8, 15, 30))
        self.assertEqual(last, 135.6)
        self.assertIsNone(prev)

    def test_empty_everything(self):
        self.assertEqual(select_fresh_close([], None, None), (None, None))

    def test_filters_null_and_nonpositive_closes(self):
        daily = [(date(2026, 6, 4), 0.0), (date(2026, 6, 5), None), (date(2026, 6, 8), 100.0)]
        last, prev = select_fresh_close(daily, None, None)
        self.assertEqual(last, 100.0)
        self.assertIsNone(prev)  # only one valid close

    def test_unsorted_input_is_sorted(self):
        daily = [(date(2026, 6, 5), 138.26), (date(2026, 6, 2), 138.83), (date(2026, 6, 4), 138.95)]
        last, prev = select_fresh_close(daily, None, None)
        self.assertEqual(last, 138.26)   # newest date wins regardless of order
        self.assertEqual(prev, 138.95)


class TestAtrStopTarget(unittest.TestCase):
    def test_atr_half_and_full(self):
        # stop = ATR/2, target = ATR
        self.assertEqual(atr_stop_target(2.58), (1.29, 2.58, True))
        self.assertEqual(atr_stop_target(4.0), (2.0, 4.0, True))

    def test_fallback_when_no_atr(self):
        self.assertEqual(atr_stop_target(None), (1.0, 2.0, False))
        self.assertEqual(atr_stop_target(0), (1.0, 2.0, False))
        self.assertEqual(atr_stop_target(-3), (1.0, 2.0, False))

    def test_custom_fallback(self):
        self.assertEqual(atr_stop_target(None, fallback_stop_pct=1.5, fallback_target_pct=3.0),
                         (1.5, 3.0, False))

    def test_sanity_caps_bind_only_on_garbage_atr(self):
        # a corrupt 30% ATR is clamped by the wide caps (10/20), not the rule
        self.assertEqual(atr_stop_target(30.0), (10.0, 20.0, True))
        # a normal liquid stock never hits the cap
        stop, target, used = atr_stop_target(3.2)
        self.assertEqual((stop, target, used), (1.6, 3.2, True))

    def test_non_numeric_atr_is_fallback(self):
        self.assertEqual(atr_stop_target("nope"), (1.0, 2.0, False))


if __name__ == '__main__':
    unittest.main()
