"""
filing_classifier.py — turn a raw exchange filing / corporate announcement into a
precise, plain-English investor alert.

PURE (stdlib `re` only; no network, DB, app state, or LLM) → import-safe,
deterministic, unit-testable. Powers the /api/filings "Exchange Filing Alerts"
feed by classifying BSE corporate announcements (and already-scraped catalyst
news) into the nine material event types a normal investor should never miss:

  promoter_pledge · insider_trading · resignation · acquisition · order_win ·
  rating_change · dividend · split · bonus

Each classified filing carries:
  • a stable machine `type` + human `type_label`
  • an investor-facing `impact` (positive / negative / neutral FOR THE STOCK)
  • a `severity` (high / medium / low) used to rank the feed
  • a one-line plain-English `explanation` ("what this means for you")
  • a `detail` string with any figures we can safely extract (₹ dividend,
    pledge %, order value, split / bonus ratio, rating agency + direction).

HONESTY CONTRACT: `impact` is the *typical* market reaction to that event type,
NOT advice and NOT a price prediction. Real reactions depend on price already
paid, size, and context — the UI frames it as "what this usually means", and
unknown directions resolve to neutral rather than a guess.
"""
import re

# ── ordered (key -> label). Order = detection priority AND default UI order.
#    More specific / higher-signal events sit first so an announcement that
#    mentions several things (e.g. "board meeting to consider dividend & bonus")
#    is bucketed by its most material catalyst.
FILING_TYPE_LABELS = {
    "promoter_pledge": "Promoter Pledge",
    "insider_trading": "Insider Trade",
    "rating_change":   "Rating Change",
    "acquisition":     "Acquisition / M&A",
    "resignation":     "Resignation",
    "order_win":       "Order Win",
    "bonus":           "Bonus Issue",
    "split":           "Stock Split",
    "dividend":        "Dividend",
}

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

# Regulatory / legal contexts that LOOK like an "order win" but are not — a SEBI
# order, a court order, an NCLT order. Guards the order_win rule.
_NON_ORDER_CONTEXT = (
    "sebi order", "court order", "nclt order", "tribunal", "show cause",
    "show-cause", "adjudicat", "penalty", "fine of", "recall order",
)


def _has(text, *needles):
    return any(n in text for n in needles)


def _clean(s):
    """Collapse whitespace; trim to a tidy one-liner."""
    return re.sub(r"\s+", " ", str(s or "")).strip()


# ──────────────────────────────────────────────────────────────────────────
# FIGURE EXTRACTORS (best-effort; all return '' when nothing is found)
# ──────────────────────────────────────────────────────────────────────────
_NUM = r"([0-9][0-9,]*(?:\.[0-9]+)?)"


def _money(text):
    """Largest rupee figure with a crore/lakh/cr scale, e.g. '₹1,250 crore'."""
    best, best_val = "", -1.0
    for m in re.finditer(
        r"(?:rs\.?|inr|₹)\s*" + _NUM + r"\s*(crore|cr\b|lakh|lakhs|billion|bn\b|million|mn\b)",
        text,
    ):
        try:
            val = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = m.group(2)
        scale = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5,
                 "billion": 1e9, "bn": 1e9, "million": 1e6, "mn": 1e6}.get(unit, 1)
        norm = val * scale
        if norm > best_val:
            best_val = norm
            unit_lbl = {"cr": "crore", "bn": "billion", "mn": "million"}.get(unit, unit)
            best = f"₹{m.group(1)} {unit_lbl}"
    return best, (best_val if best_val > 0 else 0.0)


def _percent(text):
    m = re.search(_NUM + r"\s*(?:per cent|percent|%)", text)
    return f"{m.group(1)}%" if m else ""


def _ratio(text):
    """A:B or A is to B style ratio (bonus / split)."""
    m = re.search(r"\b([0-9]+)\s*(?::|is to|for every|for)\s*([0-9]+)\b", text)
    return f"{m.group(1)}:{m.group(2)}" if m else ""


def _rupee_per_share(text):
    m = re.search(r"(?:rs\.?|inr|₹)\s*" + _NUM + r"\s*(?:per\s*(?:equity\s*)?share|/-?\s*per share|per share)", text)
    if m:
        return f"₹{m.group(1)} per share"
    # bare "dividend of Rs 5" / "Rs. 12/-"
    m = re.search(r"(?:dividend[^0-9]{0,18})(?:rs\.?|inr|₹)\s*" + _NUM, text)
    if m:
        return f"₹{m.group(1)} per share"
    return ""


# ──────────────────────────────────────────────────────────────────────────
# PER-TYPE RESOLVERS — each returns (impact, severity, explanation, detail)
# ──────────────────────────────────────────────────────────────────────────
def _resolve_pledge(t):
    released = _has(t, "release of pledge", "released", "revoke", "revocation",
                    "satisfaction of", "de-pledge", "depledge", "released the pledge")
    invoked = _has(t, "invocation", "invoked")
    pct = _percent(t)
    if invoked:
        return ("negative", "high",
                "Lenders have INVOKED a promoter pledge — they sold pledged promoter "
                "shares to recover dues. This is a serious distress signal and usually "
                "pressures the stock.",
                (f"{pct} of shares" if pct else "pledge invoked"))
    if released:
        return ("positive", "medium",
                "Promoters have RELEASED previously pledged shares, easing financial "
                "stress on the promoter group — generally reassuring for shareholders.",
                (f"{pct} released" if pct else "pledge released"))
    return ("negative", "high",
            "Promoters have pledged part of their shareholding as collateral for loans. "
            "Heavy or rising pledges are a red flag — if the stock falls, lenders can "
            "sell these shares and deepen the drop.",
            (f"{pct} of holding pledged" if pct else "fresh pledge created"))


def _resolve_insider(t):
    buy = _has(t, "acqui", "purchase", "bought", "buy ", "subscrib", "allot",
               "increase in shareholding", "market purchase")
    sell = _has(t, "dispos", "sold", " sale", "sell", "off market sale",
                "off-market sale", "reduction in shareholding", "encash", "pledge")
    if buy and not sell:
        return ("positive", "medium",
                "An insider (promoter / director / senior management) BOUGHT shares with "
                "their own money. Insider buying often signals genuine confidence in the "
                "company's prospects.",
                "insider buying")
    if sell and not buy:
        return ("negative", "medium",
                "An insider SOLD shares. Insider selling isn't always bad (personal "
                "liquidity, tax, diversification), but large or repeated sales can hint "
                "at caution.",
                "insider selling")
    return ("neutral", "low",
            "An insider (promoter / director / designated person) reported a change in "
            "their shareholding under SEBI disclosure rules. Watch whether it is buying "
            "or selling and how large it is.",
            "insider dealing disclosure")


def _resolve_rating(t):
    agency = ""
    for a, lbl in (("crisil", "CRISIL"), ("icra", "ICRA"), ("care ", "CARE"),
                   ("india ratings", "India Ratings"), ("ind-ra", "India Ratings"),
                   ("fitch", "Fitch"), ("moody", "Moody's"), ("s&p", "S&P"),
                   ("brickwork", "Brickwork"), ("acuite", "Acuité")):
        if a in t:
            agency = lbl
            break
    down = _has(t, "downgrad", "revised downward", "lowered", "cut to", "negative outlook")
    up = _has(t, "upgrad", "revised upward", "improved", "positive outlook", "raised to")
    if down and not up:
        return ("negative", "high",
                "A credit-rating agency DOWNGRADED the company (or its outlook). Weaker "
                "ratings raise borrowing costs and flag financial stress.",
                (f"{agency} downgrade" if agency else "rating downgrade"))
    if up and not down:
        return ("positive", "medium",
                "A credit-rating agency UPGRADED the company (or its outlook). Stronger "
                "ratings mean cheaper borrowing and healthier finances.",
                (f"{agency} upgrade" if agency else "rating upgrade"))
    return ("neutral", "low",
            "A credit-rating agency reviewed the company's debt rating. A reaffirmed or "
            "stable rating means no change in the agency's view of its credit health.",
            (f"{agency} rating action" if agency else "rating reaffirmed"))


def _resolve_acquisition(t):
    being_acquired = _has(t, "open offer", "acquired by", "takeover of the company",
                          "to be acquired", "stake in the company")
    if being_acquired:
        return ("positive", "high",
                "There is an acquisition / open offer involving the company itself. "
                "Acquirers usually pay a premium to existing shareholders, which can "
                "lift the stock.",
                "open offer / takeover")
    if _has(t, "demerger", "hive off", "hive-off", "spin off", "spin-off"):
        return ("positive", "medium",
                "The company is demerging / spinning off a business into a separate "
                "entity. This can unlock value by letting each business be valued on "
                "its own.",
                "demerger / spin-off")
    val, _ = _money(t)
    return ("positive", "medium",
            "The company is making an acquisition / merger. At a fair price this adds "
            "growth and scale; overpaying or taking on heavy debt to fund it can hurt.",
            (f"deal value {val}" if val else "acquisition / merger"))


def _resolve_resignation(t):
    senior = _has(t, "auditor", "chief financial", "cfo", "managing director",
                  " md ", "ceo", "chief executive", "whole-time director",
                  "whole time director", "chairman")
    role = ""
    for kw, lbl in (("auditor", "auditor"), ("cfo", "CFO"), ("chief financial", "CFO"),
                    ("ceo", "CEO"), ("chief executive", "CEO"),
                    ("managing director", "Managing Director"),
                    ("company secretary", "Company Secretary"),
                    ("chairman", "Chairman"), ("director", "director")):
        if kw in t:
            role = lbl
            break
    if senior:
        return ("negative", "high",
                "A key person (e.g. CEO / CFO / auditor / MD) is leaving. Sudden senior "
                "or auditor exits can point to governance or internal trouble and often "
                "unsettle the stock.",
                (f"{role} resignation" if role else "senior management exit"))
    return ("negative", "medium",
            "A director / official has resigned. Routine exits are usually minor, but a "
            "cluster of departures is worth watching.",
            (f"{role} resignation" if role else "resignation"))


def _resolve_order(t):
    val, norm = _money(t)
    sev = "high" if norm >= 1e9 else "medium"   # ₹100 cr+ = high
    return ("positive", sev,
            "The company has WON a new order / contract. Fresh orders build the future "
            "revenue pipeline and improve earnings visibility — usually a positive.",
            (f"order value {val}" if val else "new order / contract win"))


def _resolve_dividend(t):
    detail = _rupee_per_share(t) or (_percent(t) and f"{_percent(t)} of face value") or ""
    special = _has(t, "special dividend")
    return ("positive", "low",
            "The company declared a dividend — a cash payout to shareholders. A steady "
            "or rising dividend reflects healthy cash flows."
            + (" This is a one-off special dividend." if special else ""),
            (detail or "dividend declared"))


def _resolve_split(t):
    ratio = _ratio(t)
    fv = re.search(r"(?:rs\.?|₹)\s*([0-9]+).{0,12}?(?:to|→).{0,4}?(?:rs\.?|₹)\s*([0-9]+)", t)
    detail = ""
    if fv:
        detail = f"face value ₹{fv.group(1)} → ₹{fv.group(2)}"
    elif ratio:
        detail = f"{ratio} split"
    return ("neutral", "low",
            "The company is splitting its shares (cutting the face value). You end up "
            "with more shares at a proportionally lower price — total value is unchanged, "
            "but the stock becomes more affordable and liquid.",
            (detail or "stock split"))


def _resolve_bonus(t):
    ratio = _ratio(t)
    return ("positive", "low",
            "The company is issuing BONUS shares — free extra shares to existing holders "
            "from its reserves. Your share count rises while the price adjusts down "
            "proportionally; it signals confidence and improves liquidity.",
            (f"{ratio} bonus" if ratio else "bonus issue"))


# ──────────────────────────────────────────────────────────────────────────
# DETECTORS — (type, predicate) in PRIORITY order. First match wins.
# ──────────────────────────────────────────────────────────────────────────
def _is_pledge(t):
    return _has(t, "pledge", "encumbr", "invocation of") and not _has(t, "unpledged shares only")


def _is_insider(t):
    return (_has(t, "insider trading", "sast regulation", "pit regulation",
                 "prohibition of insider", "regulation 7", "regulation 29",
                 "regulation 30 (sast)", "disclosure under regulation 7")
            or (_has(t, "shares") and _has(t, "acquisition of shares", "disposal of shares",
                                           "sale of shares", "purchase of shares")
                and _has(t, "promoter", "director", "designated person", "insider")))


def _is_rating(t):
    if _has(t, "credit rating", "credit-rating"):
        return True
    if _has(t, "rating") and _has(t, "crisil", "icra", "care ", "india ratings",
                                  "ind-ra", "fitch", "moody", "s&p", "brickwork",
                                  "acuite", "upgrad", "downgrad", "outlook", "reaffirm",
                                  "revised", "assigned"):
        return True
    return False


def _is_acquisition(t):
    return _has(t, "acquisition", "acquire", "acquires", "acquired", "amalgamation",
                "merger", "open offer", "demerger", "scheme of arrangement",
                "takeover", "take over", "buyout", "slump sale", "hive off",
                "hive-off", "spin off", "spin-off")


def _is_resignation(t):
    return _has(t, "resign", "resignation", "steps down", "stepped down",
                "tendered", "cessation", "ceases to be", "ceased to be",
                "relieved", "demise of")


def _is_order(t):
    if _has(t, *_NON_ORDER_CONTEXT):
        return False
    if _has(t, "order win", "work order", "purchase order", "letter of award",
            "letter of intent", " loa ", "l1 bidder", "lowest bidder",
            "bags order", "bags contract", "bagged"):
        return True
    if _has(t, "order", "contract", "project") and _has(t, "win", "wins", "won",
            "secure", "secures", "secured", "bag", "bags", "awarded", "award of",
            "received", "receives", "received order", "new order"):
        return True
    return False


def _is_bonus(t):
    return _has(t, "bonus issue", "bonus share", "issue of bonus", "bonus equity",
                "recommend bonus", "bonus debenture")


def _is_split(t):
    return _has(t, "stock split", "share split", "sub-division", "subdivision",
                "sub division", "split of equity", "splitting of")


def _is_dividend(t):
    return _has(t, "dividend")


_DETECTORS = [
    ("promoter_pledge", _is_pledge,       _resolve_pledge),
    ("insider_trading", _is_insider,      _resolve_insider),
    ("rating_change",   _is_rating,       _resolve_rating),
    ("acquisition",     _is_acquisition,  _resolve_acquisition),
    ("resignation",     _is_resignation,  _resolve_resignation),
    ("order_win",       _is_order,        _resolve_order),
    ("bonus",           _is_bonus,        _resolve_bonus),
    ("split",           _is_split,        _resolve_split),
    ("dividend",        _is_dividend,     _resolve_dividend),
]


def classify_filing(text, category=None, subcategory=None):
    """
    Classify a single filing/announcement line.

    Args:
        text:        the announcement subject / headline (and optionally body).
        category:    optional BSE CATEGORYNAME hint (e.g. "Credit Rating").
        subcategory: optional BSE SUBCATNAME hint.

    Returns a dict (see module docstring) or None if `text` does not match any
    of the nine tracked material event types.
    """
    raw = _clean(text)
    if not raw:
        return None
    # Lowercased, padded so " md " / " loa " word-ish guards work at the edges.
    blob = f" {raw.lower()} {str(category or '').lower()} {str(subcategory or '').lower()} "

    for key, predicate, resolver in _DETECTORS:
        if predicate(blob):
            impact, severity, explanation, detail = resolver(blob)
            return {
                "type": key,
                "type_label": FILING_TYPE_LABELS[key],
                "impact": impact,          # positive | negative | neutral
                "severity": severity,      # high | medium | low
                "severity_rank": SEVERITY_RANK[severity],
                "explanation": explanation,
                "detail": detail,
                "headline": raw,
            }
    return None
