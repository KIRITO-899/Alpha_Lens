"""
test_model_levers.py — unit tests for the entry-edge model levers:

  * marketdata.price_resolver.captured_atr   (T1.2 freshness / "unreacted move")
  * newsproc.filing_classifier.catalyst_tier (T1.3 macro de-rate + T0.3 tagging)

Both are PURE (no I/O), so these run in milliseconds. The `tests/__init__.py`
puts backend/ on sys.path, so the sibling subpackages import directly.
"""
import unittest

from marketdata.price_resolver import captured_atr
from newsproc.filing_classifier import catalyst_tier


class TestCapturedATR(unittest.TestCase):
    def test_bullish_already_moved_up_is_positive(self):
        # +1% favourable on a 2% ATR -> 0.5 ATR already captured (alpha decaying)
        self.assertAlmostEqual(captured_atr(100.0, 101.0, 2.0, True), 0.5, places=3)

    def test_bearish_already_fell_is_positive(self):
        # bearish thesis, price already dropped 1% -> favourable -> positive
        self.assertAlmostEqual(captured_atr(100.0, 99.0, 2.0, False), 0.5, places=3)

    def test_bullish_moved_against_is_negative(self):
        # bullish but price fell -> NOT yet reacted our way -> a fresh entry
        self.assertAlmostEqual(captured_atr(100.0, 99.0, 2.0, True), -0.5, places=3)

    def test_bearish_moved_against_is_negative(self):
        self.assertAlmostEqual(captured_atr(100.0, 101.0, 2.0, False), -0.5, places=3)

    def test_no_move_is_zero(self):
        self.assertEqual(captured_atr(100.0, 100.0, 2.0, True), 0.0)

    def test_no_atr_uses_floor(self):
        # atr 0 -> floored to 0.5 so +1% favourable reads as 2.0 captured
        self.assertAlmostEqual(captured_atr(100.0, 101.0, 0.0, True), 2.0, places=3)

    def test_fail_open_on_zero_base(self):
        self.assertEqual(captured_atr(0.0, 101.0, 2.0, True), 0.0)

    def test_fail_open_on_none(self):
        self.assertEqual(captured_atr(None, 101.0, 2.0, True), 0.0)
        self.assertEqual(captured_atr(100.0, None, 2.0, True), 0.0)

    def test_fail_open_on_garbage(self):
        self.assertEqual(captured_atr("x", "y", 2.0, True), 0.0)

    def test_negative_price_fails_open(self):
        self.assertEqual(captured_atr(-100.0, 101.0, 2.0, True), 0.0)


class TestCatalystTier(unittest.TestCase):
    def test_hard_promoter_pledge(self):
        self.assertEqual(
            catalyst_tier("Promoter pledges 5% stake in XYZ Ltd"), "HARD")

    def test_hard_order_win(self):
        self.assertEqual(
            catalyst_tier("ABC bags Rs 1,250 crore order from NHAI"), "HARD")

    def test_hard_rating_change(self):
        self.assertEqual(
            catalyst_tier("CRISIL downgrades long-term rating of ABC to AA-"), "HARD")

    def test_macro_crude(self):
        self.assertEqual(
            catalyst_tier("Crude oil prices surge after OPEC output cut"), "MACRO")

    def test_macro_rbi(self):
        self.assertEqual(
            catalyst_tier("RBI keeps repo rate unchanged at 6.5%"), "MACRO")

    def test_macro_brent(self):
        self.assertEqual(
            catalyst_tier("Brent crude falls below $90 a barrel"), "MACRO")

    def test_macro_fed(self):
        self.assertEqual(
            catalyst_tier("US Fed signals one more rate hike on inflation"), "MACRO")

    def test_hard_beats_macro_when_both_present(self):
        # idiosyncratic catalyst wins even though a macro word ("oil") appears
        self.assertEqual(
            catalyst_tier("CARE downgrades rating of OilCo amid crude crash"), "HARD")

    def test_soft_generic_earnings(self):
        # earnings aren't one of the nine filing types -> SOFT (so it is NOT
        # de-rated by the macro penalty; passes at the normal bar)
        self.assertEqual(
            catalyst_tier("XYZ reports steady Q4 numbers"), "SOFT")

    def test_soft_empty(self):
        self.assertEqual(catalyst_tier(""), "SOFT")

    def test_soft_none(self):
        self.assertEqual(catalyst_tier(None), "SOFT")


if __name__ == "__main__":
    unittest.main()
