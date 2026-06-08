"""
Unit tests for the day-over-day F&O diff (#4) — signals.fno_engine.diff_snapshots
and the prev_snapshot integration into build_smart_money_board.

Pure: no network / DB / threads. Run with:
    cd backend && python -m unittest discover -s tests
"""
import unittest

from signals.fno_engine import diff_snapshots, build_smart_money_board


def _fut(px, oi_chg_total, oi_total, **extra):
    base = {
        "px_chg_pct": px, "oi_chg_total": oi_chg_total, "oi_total": oi_total,
        "oi_chg_pct": 20.0, "front_close": 100.0, "front_prev": 100.0,
        "val_cr": 50.0, "is_index": False, "fresh_oi": False,
        "front_oi": oi_total, "next_oi": 0,
    }
    base.update(extra)
    return base


class TestDiffSnapshots(unittest.TestCase):
    def test_flip_bullish_to_bearish(self):
        # AAA was long buildup (px↑ oi↑) yesterday, short buildup (px↓ oi↑) today.
        prev = {"bhavcopy_date": "2026-06-05",
                "futures": {"AAA": _fut(2.0, 5000, 100000)}}
        curr = {"futures": {"AAA": _fut(-2.0, 5000, 110000)}}
        d = diff_snapshots(curr, prev)
        vp = d["by_symbol"]["AAA"]
        self.assertTrue(vp["flipped"])
        self.assertFalse(vp["is_new"])
        self.assertEqual(vp["buildup_prev"], "LONG_BUILDUP")
        # OI grew 100000 -> 110000 = +10%
        self.assertEqual(vp["oi_delta_pct"], 10.0)
        self.assertEqual(d["summary"]["flipped_count"], 1)
        self.assertEqual(d["summary"]["prev_date"], "2026-06-05")

    def test_same_direction_not_flagged(self):
        # Both days long buildup → not a flip (same direction).
        prev = {"futures": {"AAA": _fut(2.0, 5000, 100000)}}
        curr = {"futures": {"AAA": _fut(3.0, 8000, 120000)}}
        d = diff_snapshots(curr, prev)
        self.assertFalse(d["by_symbol"]["AAA"]["flipped"])
        self.assertEqual(d["by_symbol"]["AAA"]["oi_delta_pct"], 20.0)

    def test_new_symbol(self):
        prev = {"futures": {}}
        curr = {"futures": {"BBB": _fut(2.0, 5000, 50000)}}
        d = diff_snapshots(curr, prev)
        self.assertTrue(d["by_symbol"]["BBB"]["is_new"])
        self.assertIsNone(d["by_symbol"]["BBB"]["oi_delta_pct"])
        self.assertIn("BBB", d["summary"]["new_names"])
        self.assertEqual(d["summary"]["new_count"], 1)

    def test_neutral_flip_not_counted(self):
        # A move into/out of NEUTRAL is not a bullish<->bearish flip.
        prev = {"futures": {"AAA": _fut(0.01, 100, 100000)}}   # NEUTRAL
        curr = {"futures": {"AAA": _fut(2.0, 5000, 100000)}}   # LONG_BUILDUP
        d = diff_snapshots(curr, prev)
        self.assertFalse(d["by_symbol"]["AAA"]["flipped"])

    def test_index_excluded(self):
        prev = {"futures": {"NIFTY": _fut(2.0, 5000, 1, is_index=True)}}
        curr = {"futures": {"NIFTY": _fut(-2.0, 5000, 1, is_index=True)}}
        d = diff_snapshots(curr, prev)
        self.assertNotIn("NIFTY", d["by_symbol"])

    def test_malformed_never_raises(self):
        self.assertEqual(diff_snapshots(None, None)["summary"]["flipped_count"], 0)
        self.assertEqual(diff_snapshots({}, {})["by_symbol"], {})


class TestBoardDiffIntegration(unittest.TestCase):
    def test_board_attaches_vs_prev_and_changes(self):
        prev = {"bhavcopy_date": "2026-06-05",
                "futures": {"AAA": _fut(2.0, 5000, 100000)}}
        curr = {"bhavcopy_date": "2026-06-08",
                "futures": {"AAA": _fut(-2.0, 5000, 110000)},
                "options": {}}
        board = build_smart_money_board(curr, prev_snapshot=prev)
        self.assertEqual(board["changes_since"], "2026-06-05")
        self.assertEqual(board["changes"]["flipped_count"], 1)
        # AAA is in the SHORT_BUILDUP bucket now; its row carries vs_prev.
        sb = board["buildups"]["SHORT_BUILDUP"]
        self.assertTrue(sb and sb[0]["symbol"] == "AAA")
        self.assertTrue(sb[0]["vs_prev"]["flipped"])

    def test_board_without_prev_is_backward_compatible(self):
        curr = {"bhavcopy_date": "2026-06-08",
                "futures": {"AAA": _fut(2.0, 5000, 100000)}, "options": {}}
        board = build_smart_money_board(curr)   # no prev_snapshot
        self.assertIsNone(board["changes"])
        self.assertIsNone(board["changes_since"])
        # rows must not carry a vs_prev key when there's no baseline
        lb = board["buildups"]["LONG_BUILDUP"]
        self.assertTrue(lb and "vs_prev" not in lb[0])


if __name__ == "__main__":
    unittest.main()
