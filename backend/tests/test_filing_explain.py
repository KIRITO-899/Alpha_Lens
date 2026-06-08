"""
Tests for the deterministic filing cause/explainer layer (click-to-explain).
Pure — no network/DB/LLM. Run: cd backend && python -m unittest discover -s tests
"""
import unittest

from newsproc.filing_classifier import (
    explain_filing, FILING_MECHANISMS, FILING_TYPE_LABELS, FILING_DISCLAIMER,
)


class TestFilingExplain(unittest.TestCase):
    def test_every_type_has_a_full_explainer(self):
        # Every classifiable type must have a mechanism + watch list + caveat,
        # so a clicked alert never opens an empty modal.
        for key in FILING_TYPE_LABELS:
            d = explain_filing(key)
            self.assertTrue(d, f"missing explainer for {key}")
            self.assertIn("mechanism", d)
            self.assertGreater(len(d["mechanism"]), 80, f"thin mechanism for {key}")
            self.assertIn("watch", d)
            self.assertGreaterEqual(len(d["watch"]), 2, f"too few watch bullets for {key}")
            self.assertTrue(all(isinstance(w, str) and w for w in d["watch"]))
            self.assertIn("caveat", d)
            self.assertTrue(d["caveat"])

    def test_mechanisms_cover_exactly_the_label_types(self):
        self.assertEqual(set(FILING_MECHANISMS), set(FILING_TYPE_LABELS))

    def test_unknown_type_returns_empty(self):
        self.assertEqual(explain_filing("not_a_real_type"), {})
        self.assertEqual(explain_filing(None), {})

    def test_disclaimer_present(self):
        self.assertIn("NOT advice", FILING_DISCLAIMER)


if __name__ == "__main__":
    unittest.main()
