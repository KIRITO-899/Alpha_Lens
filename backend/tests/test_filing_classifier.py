import unittest

from newsproc import filing_classifier as fc


class TestTypeDetection(unittest.TestCase):
    def _type(self, text, **kw):
        r = fc.classify_filing(text, **kw)
        return r["type"] if r else None

    def test_promoter_pledge(self):
        self.assertEqual(self._type("Creation of pledge over 12% of promoter shareholding"),
                         "promoter_pledge")

    def test_pledge_release_is_positive(self):
        r = fc.classify_filing("Release of pledge on 5% of shares by promoters")
        self.assertEqual(r["type"], "promoter_pledge")
        self.assertEqual(r["impact"], "positive")

    def test_pledge_invocation_high_severity_negative(self):
        r = fc.classify_filing("Invocation of pledge: lender sold promoter shares")
        self.assertEqual(r["type"], "promoter_pledge")
        self.assertEqual(r["impact"], "negative")
        self.assertEqual(r["severity"], "high")

    def test_insider_buy_positive(self):
        r = fc.classify_filing(
            "Disclosure under Regulation 7(2) of SAST: acquisition of shares by promoter")
        self.assertEqual(r["type"], "insider_trading")
        self.assertEqual(r["impact"], "positive")

    def test_insider_sell_negative(self):
        r = fc.classify_filing(
            "Disclosure under PIT Regulation: disposal of shares by designated person")
        self.assertEqual(r["type"], "insider_trading")
        self.assertEqual(r["impact"], "negative")

    def test_rating_downgrade_negative_high(self):
        r = fc.classify_filing("CRISIL downgrades long-term rating to A from AA-")
        self.assertEqual(r["type"], "rating_change")
        self.assertEqual(r["impact"], "negative")
        self.assertEqual(r["severity"], "high")
        self.assertIn("CRISIL", r["detail"])

    def test_rating_upgrade_positive(self):
        r = fc.classify_filing("ICRA upgrades credit rating with positive outlook")
        self.assertEqual(r["type"], "rating_change")
        self.assertEqual(r["impact"], "positive")

    def test_acquisition(self):
        self.assertEqual(self._type("Announcement of acquisition of 100% stake in XYZ Pvt Ltd"),
                         "acquisition")

    def test_open_offer_high_severity(self):
        r = fc.classify_filing("Open offer to acquire shares of the company at Rs 450")
        self.assertEqual(r["type"], "acquisition")
        self.assertEqual(r["severity"], "high")

    def test_resignation_auditor_high(self):
        r = fc.classify_filing("Resignation of Statutory Auditor with immediate effect")
        self.assertEqual(r["type"], "resignation")
        self.assertEqual(r["severity"], "high")
        self.assertEqual(r["impact"], "negative")

    def test_order_win(self):
        r = fc.classify_filing("Company bags new order worth Rs 1,250 crore from NHAI")
        self.assertEqual(r["type"], "order_win")
        self.assertEqual(r["impact"], "positive")
        self.assertEqual(r["severity"], "high")  # >= 100cr
        self.assertIn("crore", r["detail"])

    def test_dividend(self):
        r = fc.classify_filing("Board recommends final dividend of Rs 5 per equity share")
        self.assertEqual(r["type"], "dividend")
        self.assertIn("per share", r["detail"])

    def test_bonus(self):
        r = fc.classify_filing("Board recommends bonus issue in the ratio of 1:1")
        self.assertEqual(r["type"], "bonus")
        self.assertEqual(r["detail"], "1:1 bonus")

    def test_split(self):
        r = fc.classify_filing("Sub-division of equity shares (stock split)")
        self.assertEqual(r["type"], "split")
        self.assertEqual(r["impact"], "neutral")


class TestPriorityAndGuards(unittest.TestCase):
    def test_bonus_beats_dividend_when_both_present(self):
        # Bonus is rarer/more material → wins the primary bucket.
        self.assertEqual(
            fc.classify_filing("Board to consider dividend and bonus issue")["type"],
            "bonus")

    def test_rating_beats_dividend(self):
        self.assertEqual(
            fc.classify_filing("CARE reaffirms rating; also declares dividend")["type"],
            "rating_change")

    def test_sebi_order_is_not_order_win(self):
        # A SEBI/court order must NOT be misread as an order win.
        self.assertNotEqual(self._safe("SEBI passes order imposing penalty on the company"),
                            "order_win")

    def test_court_order_not_order_win(self):
        self.assertNotEqual(self._safe("High Court order in pending litigation matter"),
                            "order_win")

    def test_category_hint_used(self):
        r = fc.classify_filing("Outcome of meeting", category="Credit Rating")
        self.assertEqual(r["type"], "rating_change")

    def _safe(self, text):
        r = fc.classify_filing(text)
        return r["type"] if r else None


class TestSafety(unittest.TestCase):
    def test_unrelated_returns_none(self):
        self.assertIsNone(fc.classify_filing("Quarterly results conference call intimation"))

    def test_empty_returns_none(self):
        self.assertIsNone(fc.classify_filing(""))
        self.assertIsNone(fc.classify_filing(None))

    def test_every_result_has_required_keys(self):
        r = fc.classify_filing("Promoter pledge created over 10% holding")
        for k in ("type", "type_label", "impact", "severity", "severity_rank",
                  "explanation", "detail", "headline"):
            self.assertIn(k, r)
        self.assertIn(r["impact"], ("positive", "negative", "neutral"))
        self.assertIn(r["severity"], ("high", "medium", "low"))

    def test_labels_cover_all_types(self):
        for key in fc.FILING_TYPE_LABELS:
            self.assertTrue(fc.FILING_TYPE_LABELS[key])


if __name__ == "__main__":
    unittest.main()
