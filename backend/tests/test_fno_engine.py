import unittest

from signals.fno_engine import (
    classify_buildup, pcr, max_pain, oi_walls, option_sentiment,
    conviction_score, sector_for, option_chain_view, build_smart_money_board,
    normalize_ticker, MIN_VAL_CR,
)
from marketdata.oi_data import _parse_bhavcopy_full


# ── A small synthetic option chain used by several tests ──────────────────
_CHAIN = [
    {"strike": 100, "ce_oi": 10,  "pe_oi": 100, "ce_chg": 0, "pe_chg": 0},
    {"strike": 110, "ce_oi": 50,  "pe_oi": 50,  "ce_chg": 0, "pe_chg": 0},
    {"strike": 120, "ce_oi": 100, "pe_oi": 10,  "ce_chg": 0, "pe_chg": 0},
]


class TestBuildupClassification(unittest.TestCase):
    def test_four_quadrants(self):
        self.assertEqual(classify_buildup(2.0, 5000), "LONG_BUILDUP")    # px↑ oi↑
        self.assertEqual(classify_buildup(2.0, -5000), "SHORT_COVERING")  # px↑ oi↓
        self.assertEqual(classify_buildup(-2.0, 5000), "SHORT_BUILDUP")   # px↓ oi↑
        self.assertEqual(classify_buildup(-2.0, -5000), "LONG_UNWINDING") # px↓ oi↓

    def test_neutral_deadzone(self):
        self.assertEqual(classify_buildup(0.01, 9999), "NEUTRAL")
        self.assertEqual(classify_buildup(None, None), "NEUTRAL")


class TestOptionMath(unittest.TestCase):
    def test_pcr(self):
        self.assertEqual(pcr(160, 160), 1.0)
        self.assertEqual(pcr(100, 150), 1.5)
        self.assertIsNone(pcr(0, 100))   # divide-by-zero guard

    def test_max_pain(self):
        # Hand-computed: total buyer-ITM value is minimized at strike 110.
        self.assertEqual(max_pain(_CHAIN), 110)
        self.assertIsNone(max_pain([]))

    def test_oi_walls(self):
        call_wall, put_wall = oi_walls(_CHAIN)
        self.assertEqual(call_wall, 120)   # max CE OI → resistance
        self.assertEqual(put_wall, 100)    # max PE OI → support

    def test_option_sentiment(self):
        self.assertEqual(option_sentiment(1.6, 100, 300)[0], "BULLISH")   # high PCR + put writing
        self.assertEqual(option_sentiment(0.5, 300, 100)[0], "BEARISH")   # low PCR + call writing
        self.assertEqual(option_sentiment(1.0, 100, 100)[0], "NEUTRAL")


class TestConviction(unittest.TestCase):
    def test_components_and_clamp(self):
        # 38 base + 25 OI + min(4*2.5,15)=10 + 8 (val>=50) + 8 (deliv>=60) = 89
        self.assertEqual(conviction_score(25, 4, 100, 70), 89)

    def test_floor_and_ceiling(self):
        self.assertEqual(conviction_score(0, 0, 0), 38)
        self.assertLessEqual(conviction_score(999, 999, 999, 999), 99)

    def test_delivery_optional(self):
        # No delivery → no delivery bonus
        self.assertEqual(conviction_score(10, 2, 5), 38 + 10 + 5)


class TestSectorMap(unittest.TestCase):
    def test_known_and_unknown(self):
        self.assertEqual(sector_for("RELIANCE"), "Energy")
        self.assertEqual(sector_for("HDFCBANK"), "Banks")
        self.assertEqual(sector_for("INFY.NS"), "IT")        # normalization
        self.assertEqual(sector_for("ZZ_UNLISTED"), "Other")


class TestOptionChainView(unittest.TestCase):
    def test_integrates(self):
        entry = {
            "expiry": "2026-06-25", "spot": 110, "is_index": False,
            "ce_oi": 160, "pe_oi": 160, "ce_chg": 0, "pe_chg": 0,
            "strikes": _CHAIN,
        }
        v = option_chain_view("XYZ", entry)
        self.assertEqual(v["pcr"], 1.0)
        self.assertEqual(v["max_pain"], 110)
        self.assertEqual(v["call_wall"], 120)
        self.assertEqual(v["put_wall"], 100)
        self.assertEqual(len(v["ladder"]), 3)

    def test_empty(self):
        self.assertIsNone(option_chain_view("X", None))


def _board_snapshot():
    return {
        "bhavcopy_date": "2026-06-05",
        "fetched_at": "2026-06-05T13:00:00+00:00",
        "futures": {
            "RELIANCE":  {"oi_total": 120000, "oi_chg_total": 20000, "oi_chg_pct": 20.0,
                          "px_chg_pct": 2.5, "front_close": 2900, "val_cr": 800},
            "TATASTEEL": {"oi_total": 90000, "oi_chg_total": 15000, "oi_chg_pct": 16.0,
                          "px_chg_pct": -1.8, "front_close": 150, "val_cr": 300},
            "INFY":      {"oi_total": 50000, "oi_chg_total": -8000, "oi_chg_pct": -13.0,
                          "px_chg_pct": 1.2, "front_close": 1500, "val_cr": 200},
            "TINYCO":    {"oi_total": 10, "oi_chg_total": 5, "oi_chg_pct": 100.0,
                          "px_chg_pct": 5.0, "front_close": 10, "val_cr": 0.2},  # thin
        },
        "options": {
            "NIFTY": {
                "is_index": True, "expiry": "2026-06-25", "spot": 22050,
                "ce_oi": 1000, "pe_oi": 1500, "ce_chg": 100, "pe_chg": 300,
                "strikes": [
                    {"strike": 21800, "ce_oi": 200, "pe_oi": 800},
                    {"strike": 22000, "ce_oi": 300, "pe_oi": 500},
                    {"strike": 22200, "ce_oi": 500, "pe_oi": 200},
                ],
            },
        },
    }


class TestBoard(unittest.TestCase):
    def setUp(self):
        self.board = build_smart_money_board(
            _board_snapshot(), watchlist=["RELIANCE"], delivery={"RELIANCE": 68.0},
            deals=[{"symbol": "TATASTEEL", "side": "SELL", "kind": "bulk"}],
        )

    def test_universe_and_counts(self):
        self.assertEqual(self.board["universe_count"], 4)
        # TINYCO is a long buildup by sign, so the COUNT is 2…
        self.assertEqual(self.board["counts"]["Long Buildup"], 2)

    def test_thin_name_filtered_from_tables(self):
        # …but TINYCO (val_cr 0.2 < MIN_VAL_CR) is dropped from the ranked table.
        lb_syms = [r["symbol"] for r in self.board["buildups"]["LONG_BUILDUP"]]
        self.assertIn("RELIANCE", lb_syms)
        self.assertNotIn("TINYCO", lb_syms)

    def test_quadrant_routing(self):
        self.assertEqual(self.board["buildups"]["SHORT_BUILDUP"][0]["symbol"], "TATASTEEL")
        self.assertEqual(self.board["buildups"]["SHORT_COVERING"][0]["symbol"], "INFY")

    def test_index_matrix(self):
        nifty = next(i for i in self.board["index_matrix"] if i["symbol"] == "NIFTY")
        self.assertEqual(nifty["pcr"], 1.5)
        self.assertEqual(nifty["max_pain"], 22000)
        self.assertEqual(nifty["call_wall"], 22200)
        self.assertEqual(nifty["put_wall"], 21800)
        self.assertEqual(nifty["sentiment"], "BULLISH")

    def test_market_bias_is_net_bullish(self):
        # 2 strong longs + 1 short-cover vs 1 short, plus NIFTY PCR 1.5 overlay
        self.assertGreater(self.board["market_bias"]["score"], 0)

    def test_watchlist_slice(self):
        self.assertEqual(len(self.board["watchlist"]), 1)
        self.assertEqual(self.board["watchlist"][0]["symbol"], "RELIANCE")
        self.assertTrue(self.board["watchlist"][0]["in_watchlist"])

    def test_delivery_boosts_conviction(self):
        rel = next(r for r in self.board["buildups"]["LONG_BUILDUP"] if r["symbol"] == "RELIANCE")
        self.assertEqual(rel["delivery_pct"], 68.0)

    def test_narrative_nonempty(self):
        self.assertIsInstance(self.board["narrative"], str)
        self.assertTrue(len(self.board["narrative"]) > 20)

    def test_deals_passthrough(self):
        self.assertEqual(len(self.board["deals"]), 1)


class TestBoardSafety(unittest.TestCase):
    def test_empty_inputs(self):
        for arg in ({}, None, {"futures": {}, "options": {}}):
            b = build_smart_money_board(arg)
            self.assertFalse(b["applicable"])
            self.assertEqual(b["universe_count"], 0)
            self.assertEqual(b["market_bias"]["label"], "NEUTRAL")


# ── Parser tests (the bhavcopy → futures+options extraction) ──────────────
_BHAV_CSV = (
    "TckrSymb,FinInstrmTp,OptnTp,StrkPric,XpryDt,OpnIntrst,ChngInOpnIntrst,"
    "ClsPric,PrvsClsgPric,UndrlygPric,TtlTradgVol,TtlTrfVal\n"
    "RELIANCE,STF,,,2026-06-25,100000,5000,2900,2850,2895,1000,290000000000\n"
    "RELIANCE,STF,,,2026-07-30,20000,2000,2910,2860,2895,200,58000000000\n"
    "RELIANCE,STO,CE,2900,2026-06-25,5000,500,30,28,2895,400,0\n"
    "RELIANCE,STO,PE,2900,2026-06-25,7000,800,25,27,2895,500,0\n"
    "NIFTY,IDO,CE,22000,2026-06-25,1000,100,120,110,22010,900,0\n"
    "NIFTY,IDO,PE,22000,2026-06-25,1500,300,90,80,22010,1200,0\n"
)


class TestBhavcopyParser(unittest.TestCase):
    def setUp(self):
        self.parsed = _parse_bhavcopy_full(_BHAV_CSV)

    def test_futures_aggregate_oi(self):
        rel = self.parsed["futures"]["RELIANCE"]
        self.assertEqual(rel["oi_total"], 120000)      # 100000 + 20000
        self.assertEqual(rel["oi_chg_total"], 7000)    # 5000 + 2000

    def test_futures_front_month_price_change(self):
        rel = self.parsed["futures"]["RELIANCE"]
        # front expiry = 2026-06-25 → close 2900, prev 2850
        self.assertEqual(rel["front_xpry"], "2026-06-25")
        self.assertAlmostEqual(rel["px_chg_pct"], 1.754, places=2)

    def test_options_parsed_for_stock_and_index(self):
        rel = self.parsed["options"]["RELIANCE"]
        self.assertFalse(rel["is_index"])
        self.assertEqual(rel["ce_oi"], 5000)
        self.assertEqual(rel["pe_oi"], 7000)
        self.assertAlmostEqual(rel["spot"], 2895.0, places=1)

        nifty = self.parsed["options"]["NIFTY"]
        self.assertTrue(nifty["is_index"])
        self.assertEqual(nifty["ce_oi"], 1000)
        self.assertEqual(nifty["pe_oi"], 1500)

    def test_buildup_end_to_end(self):
        # RELIANCE: front px +1.75%, OI +7000 → LONG_BUILDUP
        rel = self.parsed["futures"]["RELIANCE"]
        self.assertEqual(classify_buildup(rel["px_chg_pct"], rel["oi_chg_total"]),
                         "LONG_BUILDUP")

    def test_empty_csv_safe(self):
        out = _parse_bhavcopy_full("TckrSymb,FinInstrmTp\n")
        self.assertEqual(out["futures"], {})
        self.assertEqual(out["options"], {})


if __name__ == "__main__":
    unittest.main()
