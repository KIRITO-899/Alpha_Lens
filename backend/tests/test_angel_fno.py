"""
Unit tests for the PURE parts of the Angel One intraday F&O source (#5):
marketdata.angel_fno.assemble_futures / assemble_index_chain, plus the
safe-by-default gating (is_enabled / get_intraday_snapshot off without the flag).

The live Angel calls (scrip master, batch quotes, threading) need real creds + a
non-datacenter IP and are validated locally — they are NOT exercised here.

Run: cd backend && python -m unittest discover -s tests
"""
import os
import unittest

from marketdata import angel_fno
from signals.fno_engine import classify_buildup, build_smart_money_board


class TestAssembleFutures(unittest.TestCase):
    def test_long_buildup_from_live_oi(self):
        # Price +10% (110 vs 100 close), OI 10000 -> 11000 (+1000) => LONG_BUILDUP.
        quotes = [{"symbolToken": "111", "ltp": 110, "close": 100,
                   "opnInterest": 11000, "tradeVolume": 1000000}]
        token_to_name = {"111": "AAA"}
        baseline = {"AAA": {"front_oi": 10000}}
        fut = angel_fno.assemble_futures(quotes, token_to_name, baseline)
        row = fut["AAA"]
        self.assertEqual(row["oi_total"], 11000)
        self.assertEqual(row["oi_chg_total"], 1000)
        self.assertEqual(row["oi_chg_pct"], 10.0)
        self.assertAlmostEqual(row["px_chg_pct"], 10.0, places=2)
        self.assertFalse(row["is_index"])
        self.assertEqual(classify_buildup(row["px_chg_pct"], row["oi_chg_total"]), "LONG_BUILDUP")

    def test_short_buildup_and_index_flag(self):
        # Price -2%, OI up => SHORT_BUILDUP; NIFTY flagged as index.
        quotes = [{"symbolToken": "260", "ltp": 98, "close": 100,
                   "opnInterest": 5500, "tradeVolume": 2000}]
        fut = angel_fno.assemble_futures(quotes, {"260": "NIFTY"}, {"NIFTY": {"front_oi": 5000}})
        row = fut["NIFTY"]
        self.assertTrue(row["is_index"])
        self.assertEqual(classify_buildup(row["px_chg_pct"], row["oi_chg_total"]), "SHORT_BUILDUP")

    def test_fresh_contract_no_baseline(self):
        quotes = [{"symbolToken": "9", "ltp": 50, "close": 49, "opnInterest": 4000, "tradeVolume": 10}]
        fut = angel_fno.assemble_futures(quotes, {"9": "BBB"}, {})   # no baseline
        self.assertTrue(fut["BBB"]["fresh_oi"])
        self.assertEqual(fut["BBB"]["oi_chg_pct"], 200.0)

    def test_unknown_token_skipped_and_never_raises(self):
        fut = angel_fno.assemble_futures([{"symbolToken": "zzz", "ltp": 1}], {"111": "AAA"}, {})
        self.assertEqual(fut, {})
        self.assertEqual(angel_fno.assemble_futures(None, {}, None), {})


class TestAssembleIndexChain(unittest.TestCase):
    def test_chain_assembly_and_deltas(self):
        quotes = [
            {"symbolToken": "c1", "ltp": 120, "opnInterest": 800},   # 24000 CE
            {"symbolToken": "p1", "ltp": 90, "opnInterest": 1500},   # 24000 PE
            {"symbolToken": "c2", "ltp": 60, "opnInterest": 400},    # 24500 CE
        ]
        token_meta = {
            "c1": {"strike": 24000, "opt_type": "CE"},
            "p1": {"strike": 24000, "opt_type": "PE"},
            "c2": {"strike": 24500, "opt_type": "CE"},
        }
        baseline = {24000: {"ce_oi": 700, "pe_oi": 1000}}   # ce +100, pe +500
        entry = angel_fno.assemble_index_chain(quotes, token_meta, baseline, spot=24050, expiry="2026-06-25")
        self.assertTrue(entry["is_index"])
        self.assertEqual(entry["expiry"], "2026-06-25")
        self.assertEqual(entry["spot"], 24050.0)
        self.assertEqual(len(entry["strikes"]), 2)            # 24000 + 24500
        self.assertEqual(entry["ce_oi"], 1200)               # 800 + 400
        self.assertEqual(entry["pe_oi"], 1500)
        s24000 = next(s for s in entry["strikes"] if s["strike"] == 24000)
        self.assertEqual(s24000["ce_chg"], 100)              # 800 - 700
        self.assertEqual(s24000["pe_chg"], 500)              # 1500 - 1000
        self.assertEqual(s24000["ce_settle"], 120.0)         # intraday mark for IV

    def test_board_consumes_intraday_shape(self):
        # An intraday-shaped snapshot must feed build_smart_money_board cleanly.
        fut = angel_fno.assemble_futures(
            [{"symbolToken": "1", "ltp": 110, "close": 100, "opnInterest": 12000, "tradeVolume": 5_000_000}],
            {"1": "RELIANCE"}, {"RELIANCE": {"front_oi": 10000}})
        board = build_smart_money_board({"bhavcopy_date": "2026-06-08", "source": "intraday",
                                         "futures": fut, "options": {}})
        self.assertTrue(board["applicable"])
        self.assertEqual(board["source"], "intraday")


class TestGatingSafeByDefault(unittest.TestCase):
    def test_disabled_without_flag(self):
        # With ANGEL_FNO_ENABLED unset, the source must be inert.
        old = os.environ.pop("ANGEL_FNO_ENABLED", None)
        try:
            self.assertFalse(angel_fno.is_enabled())
            self.assertIsNone(angel_fno.get_intraday_snapshot({"futures": {}, "options": {}}))
        finally:
            if old is not None:
                os.environ["ANGEL_FNO_ENABLED"] = old


if __name__ == "__main__":
    unittest.main()
