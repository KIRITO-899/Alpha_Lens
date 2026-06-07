"""
F&O Smart-Money engine — pure, deterministic institutional-positioning analytics.

NO network, NO DB, NO LLM. Takes a parsed bhavcopy snapshot (from
marketdata.oi_data.get_fno_raw_snapshot) and produces the F&O Smart-Money board:
the read a derivatives desk would build from the daily OI tape.

What it computes (all from the daily F&O bhavcopy — futures + options):

  • Buildup quadrants (futures, OI×price):
        LONG_BUILDUP   price↑ OI↑  — fresh longs (bullish)
        SHORT_BUILDUP  price↓ OI↑  — fresh shorts (bearish)
        SHORT_COVERING price↑ OI↓  — shorts exiting (bullish, weaker)
        LONG_UNWINDING price↓ OI↓  — longs exiting (bearish, weaker)
  • Conviction score per name (OI-surge × price-confirm × liquidity × delivery).
  • Unusual OI surges (|ΔOI%| outliers) — aggressive positioning.
  • Option chain analytics per symbol: PCR(OI), max-pain, call/put OI walls,
    fresh writing/unwinding from ΔOI, an option-sentiment read.
  • Index option matrix (NIFTY / BANKNIFTY / FINNIFTY …) — the headline numbers.
  • Sector clustering of buildups (static F&O sector map, no fundamentals calls).
  • Market-wide institutional bias (conviction-weighted long vs short pressure,
    overlaid with NIFTY PCR).
  • A deterministic, English institutional narrative (zero API keys).

Design mirrors signals/ripple_engine.py: pure functions, module-constant
tunables, fully unit-testable, instant, reproducible, never hallucinates.
"""
from __future__ import annotations

# ── Tunables (module constants → keep the module import-pure) ──────────────
NEUTRAL_PX_PCT = 0.05        # |price move| below this = NEUTRAL buildup
UNUSUAL_OI_PCT = 18.0        # |ΔOI%| at/above this = "unusual" surge
MIN_VAL_CR = 1.0             # below this futures turnover (₹cr) = thin, deprioritized
MAX_LIST = 12                # max rows per buildup table
MAX_UNUSUAL = 10
MAX_DELIVERY = 10
BULLISH_BIAS_CUT = 12.0      # bias score (-100..100) thresholds
BEARISH_BIAS_CUT = -12.0
PCR_BULL = 1.20              # index/stock PCR sentiment bands
PCR_BULL_STRONG = 1.50
PCR_BEAR = 0.80
PCR_BEAR_STRONG = 0.60

# Display order + labels for the index option matrix
INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "SENSEX", "BANKEX"]
INDEX_LABELS = {
    "NIFTY": "Nifty 50", "BANKNIFTY": "Bank Nifty", "FINNIFTY": "Fin Nifty",
    "MIDCPNIFTY": "Midcap Nifty", "NIFTYNXT50": "Nifty Next 50",
    "SENSEX": "Sensex", "BANKEX": "Bankex",
}

# ── Static F&O sector map (top ~190 liquid NSE F&O names) ──────────────────
# Lets us cluster positioning by sector with ZERO per-ticker fundamentals
# lookups. Unknown symbols fall back to "Other".
_SECTOR_GROUPS = {
    "Banks": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "INDUSINDBK",
              "BANKBARODA", "PNB", "FEDERALBNK", "IDFCFIRSTB", "AUBANK", "BANDHANBNK",
              "RBLBANK", "CANBK", "INDIANB", "UNIONBANK", "BANKINDIA"],
    "Financials": ["BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SHRIRAMFIN", "MUTHOOTFIN",
                   "LICHSGFIN", "M&MFIN", "PEL", "SBICARD", "HDFCLIFE", "SBILIFE",
                   "ICICIPRULI", "ICICIGI", "LICI", "HDFCAMC", "PFC", "RECLTD", "IRFC",
                   "POLICYBZR", "PAYTM", "ABCAPITAL", "MANAPPURAM", "IEX", "BSE",
                   "ANGELONE", "CDSL", "MCX", "HUDCO"],
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "LTTS", "MPHASIS",
           "COFORGE", "PERSISTENT", "OFSS", "TATAELXSI"],
    "Auto": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT",
             "TVSMOTOR", "ASHOKLEY", "BHARATFORG", "MOTHERSON", "BOSCHLTD",
             "BALKRISIND", "MRF", "TIINDIA", "EXIDEIND"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL", "SAIL",
               "NMDC", "NATIONALUM", "HINDZINC", "APLAPOLLO", "JSL", "HINDCOPPER"],
    "Energy": ["RELIANCE", "ONGC", "IOC", "BPCL", "HPCL", "GAIL", "PETRONET", "OIL",
               "IGL", "MGL", "GUJGASLTD", "ATGL", "ADANIGREEN", "ADANIENSOL", "COALINDIA"],
    "Power": ["NTPC", "POWERGRID", "TATAPOWER", "ADANIPOWER", "JSWENERGY", "NHPC",
              "SJVN", "TORNTPOWER", "CESC"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA", "LUPIN",
               "ALKEM", "TORNTPHARM", "BIOCON", "ZYDUSLIFE", "GLENMARK", "LAURUSLABS",
               "GRANULES", "SYNGENE", "MANKIND"],
    "Healthcare": ["APOLLOHOSP", "MAXHEALTH", "FORTIS", "LALPATHLAB", "METROPOLIS"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO",
             "GODREJCP", "COLPAL", "TATACONSUM", "UBL", "UNITDSPR", "VBL", "PGHH",
             "EMAMILTD", "RADICO"],
    "Cement": ["ULTRACEMCO", "SHREECEM", "AMBUJACEM", "ACC", "DALBHARAT", "RAMCOCEM",
               "JKCEMENT", "INDIACEM"],
    "Infra": ["LT", "ADANIPORTS", "GMRINFRA", "GMRAIRPORT", "IRB", "NCC", "NBCC",
              "RVNL", "IRCON", "KEC", "CONCOR", "IRCTC"],
    "Realty": ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "LODHA", "PHOENIXLTD", "BRIGADE"],
    "Telecom": ["BHARTIARTL", "IDEA", "INDUSTOWER", "TATACOMM", "HFCL"],
    "Chemicals": ["PIDILITIND", "SRF", "UPL", "PIIND", "AARTIIND", "DEEPAKNTR",
                  "NAVINFLUOR", "TATACHEM", "ATUL", "GNFC", "CHAMBLFERT", "COROMANDEL",
                  "FACT", "SUMICHEM"],
    "Consumer": ["TITAN", "DMART", "TRENT", "ASIANPAINT", "BERGEPAINT", "HAVELLS",
                 "VOLTAS", "CROMPTON", "DIXON", "KAJARIACER", "BATAINDIA", "RELAXO",
                 "PAGEIND", "ABFRL", "NYKAA", "KALYANKJIL", "JUBLFOOD", "INDHOTEL"],
    "Capital Goods": ["SIEMENS", "ABB", "BHEL", "BEL", "HAL", "CUMMINSIND", "THERMAX",
                      "POLYCAB", "MAZDOCK", "BDL", "SOLARINDS", "CGPOWER"],
    "Media": ["ZEEL", "SUNTV", "PVRINOX", "NETWORK18"],
    "Diversified": ["ADANIENT", "GRASIM", "ABFRL"],
    "PSU": ["GMDCLTD", "BEML", "COCHINSHIP", "IREDA", "NLCINDIA", "MOIL"],
}
_SYM_SECTOR = {}
for _sec, _syms in _SECTOR_GROUPS.items():
    for _s in _syms:
        _SYM_SECTOR.setdefault(_s, _sec)


def normalize_ticker(t):
    return (t or "").upper().replace(".NS", "").replace(".BO", "").strip()


def sector_for(symbol):
    return _SYM_SECTOR.get(normalize_ticker(symbol), "Other")


# ── Buildup classification ────────────────────────────────────────────────
def classify_buildup(px_chg_pct, oi_chg):
    """Map (price %change, OI change) → one of the four quadrants or NEUTRAL."""
    try:
        px = float(px_chg_pct or 0.0)
        oi = float(oi_chg or 0.0)
    except (ValueError, TypeError):
        return "NEUTRAL"
    if abs(px) < NEUTRAL_PX_PCT:
        return "NEUTRAL"
    px_up, oi_up = px > 0, oi > 0
    if px_up and oi_up:
        return "LONG_BUILDUP"
    if px_up and not oi_up:
        return "SHORT_COVERING"
    if not px_up and oi_up:
        return "SHORT_BUILDUP"
    return "LONG_UNWINDING"


BUILDUP_META = {
    "LONG_BUILDUP":   {"label": "Long Buildup",   "dir": "bullish", "strong": True},
    "SHORT_COVERING": {"label": "Short Covering",  "dir": "bullish", "strong": False},
    "SHORT_BUILDUP":  {"label": "Short Buildup",   "dir": "bearish", "strong": True},
    "LONG_UNWINDING": {"label": "Long Unwinding",  "dir": "bearish", "strong": False},
    "NEUTRAL":        {"label": "Neutral",         "dir": "neutral", "strong": False},
}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def conviction_score(oi_chg_pct, px_chg_pct, val_cr, delivery_pct=None):
    """0–99 conviction that the futures move reflects real positioning.

    Aggressive OI change is the spine; price confirmation, liquidity and a
    delivery spike add weight.
    """
    oi_mag = abs(float(oi_chg_pct or 0.0))
    px_mag = abs(float(px_chg_pct or 0.0))
    score = 38.0
    score += min(oi_mag, 30.0)                 # OI surge (cap +30)
    score += min(px_mag * 2.5, 15.0)           # price confirmation (cap +15)
    if val_cr and val_cr >= 50:                # liquid name
        score += 8.0
    elif val_cr and val_cr >= 10:
        score += 4.0
    if delivery_pct is not None and delivery_pct >= 60:
        score += 8.0                           # strong delivery → genuine accumulation
    elif delivery_pct is not None and delivery_pct >= 45:
        score += 4.0
    return int(round(_clamp(score, 0.0, 99.0)))


# ── Option analytics ──────────────────────────────────────────────────────
def pcr(ce_oi, pe_oi):
    ce = float(ce_oi or 0.0)
    pe = float(pe_oi or 0.0)
    if ce <= 0:
        return None
    return round(pe / ce, 2)


def max_pain(strikes):
    """Strike that minimizes total ITM value to option BUYERS (writers' max pain).

    Price tends to gravitate toward this level into expiry.
    strikes: list of {strike, ce_oi, pe_oi}.
    """
    ks = [s for s in (strikes or []) if s.get("strike")]
    if not ks:
        return None
    best_k, best_loss = None, None
    for cand in ks:
        K0 = cand["strike"]
        total = 0.0
        for s in ks:
            K = s["strike"]
            if K0 > K:                          # calls ITM at expiry price K0
                total += (s.get("ce_oi") or 0) * (K0 - K)
            elif K0 < K:                        # puts ITM
                total += (s.get("pe_oi") or 0) * (K - K0)
        if best_loss is None or total < best_loss:
            best_loss, best_k = total, K0
    return best_k


def oi_walls(strikes):
    """(call_wall, put_wall) — strikes with the largest call / put OI.

    Call wall ≈ resistance; put wall ≈ support.
    """
    call_wall = put_wall = None
    best_ce = best_pe = -1
    for s in (strikes or []):
        ce = s.get("ce_oi") or 0
        pe = s.get("pe_oi") or 0
        if ce > best_ce:
            best_ce, call_wall = ce, s.get("strike")
        if pe > best_pe:
            best_pe, put_wall = pe, s.get("strike")
    return call_wall, put_wall


def option_sentiment(pcr_val, ce_chg, pe_chg):
    """Directional read from PCR level + fresh option writing (ΔOI)."""
    score = 0
    if pcr_val is not None:
        if pcr_val >= PCR_BULL_STRONG:
            score += 2
        elif pcr_val >= PCR_BULL:
            score += 1
        elif pcr_val <= PCR_BEAR_STRONG:
            score -= 2
        elif pcr_val <= PCR_BEAR:
            score -= 1
    # Fresh writing: puts written (pe_chg↑) → support → bullish; calls written → bearish
    cec = float(ce_chg or 0.0)
    pec = float(pe_chg or 0.0)
    if pec - cec > 0:
        score += 1
    elif cec - pec > 0:
        score -= 1
    if score >= 2:
        return "BULLISH", score
    if score <= -2:
        return "BEARISH", score
    return "NEUTRAL", score


def option_chain_view(symbol, opt_entry):
    """Per-symbol option analytics + full strike ladder (for the drill-down)."""
    if not opt_entry:
        return None
    strikes = opt_entry.get("strikes") or []
    ce_oi = opt_entry.get("ce_oi", 0)
    pe_oi = opt_entry.get("pe_oi", 0)
    ce_chg = opt_entry.get("ce_chg", 0)
    pe_chg = opt_entry.get("pe_chg", 0)
    spot = opt_entry.get("spot", 0.0)
    p = pcr(ce_oi, pe_oi)
    mp = max_pain(strikes)
    cw, pw = oi_walls(strikes)
    sentiment, sent_score = option_sentiment(p, ce_chg, pe_chg)
    mp_gap = None
    if mp and spot:
        mp_gap = round((spot - mp) / mp * 100, 2)   # +ve → spot above max pain
    return {
        "symbol": normalize_ticker(symbol),
        "is_index": bool(opt_entry.get("is_index")),
        "expiry": opt_entry.get("expiry"),
        "spot": spot,
        "pcr": p,
        "max_pain": mp,
        "max_pain_gap_pct": mp_gap,
        "call_wall": cw,
        "put_wall": pw,
        "ce_oi": ce_oi, "pe_oi": pe_oi,
        "ce_chg": ce_chg, "pe_chg": pe_chg,
        "sentiment": sentiment,
        "sentiment_score": sent_score,
        "ladder": strikes,
    }


# ── Board assembly ────────────────────────────────────────────────────────
def _fmt_pct(v):
    try:
        return round(float(v), 2)
    except (ValueError, TypeError):
        return 0.0


def _build_row(sym, fut, opt_entry, delivery_pct, watchset):
    px = _fmt_pct(fut.get("px_chg_pct"))
    oi_chg_pct = _fmt_pct(fut.get("oi_chg_pct"))
    val_cr = _fmt_pct(fut.get("val_cr"))
    buildup = classify_buildup(px, fut.get("oi_chg_total"))
    conv = conviction_score(oi_chg_pct, px, val_cr, delivery_pct)
    p = pcr(opt_entry.get("ce_oi"), opt_entry.get("pe_oi")) if opt_entry else None
    return {
        "symbol": sym,
        "sector": sector_for(sym),
        "buildup": buildup,
        "buildup_label": BUILDUP_META[buildup]["label"],
        "direction": BUILDUP_META[buildup]["dir"],
        "px_chg_pct": px,
        "oi_chg_pct": oi_chg_pct,
        "oi": fut.get("oi_total", 0),
        "close": _fmt_pct(fut.get("front_close")),
        "val_cr": val_cr,
        "conviction": conv,
        "pcr": p,
        "delivery_pct": (round(delivery_pct, 1) if delivery_pct is not None else None),
        "in_watchlist": sym in watchset,
    }


def _index_matrix(options):
    out = []
    for sym in INDEX_SYMBOLS:
        ent = options.get(sym)
        if not ent:
            continue
        view = option_chain_view(sym, ent)
        if not view:
            continue
        out.append({
            "symbol": sym,
            "label": INDEX_LABELS.get(sym, sym),
            "spot": view["spot"],
            "pcr": view["pcr"],
            "max_pain": view["max_pain"],
            "max_pain_gap_pct": view["max_pain_gap_pct"],
            "call_wall": view["call_wall"],
            "put_wall": view["put_wall"],
            "sentiment": view["sentiment"],
            "ce_chg": view["ce_chg"],
            "pe_chg": view["pe_chg"],
        })
    return out


def _sector_clustering(rows):
    """Net conviction-weighted bias per sector (only sectors with ≥2 names)."""
    agg = {}
    for r in rows:
        sec = r["sector"]
        d = BUILDUP_META[r["buildup"]]["dir"]
        a = agg.setdefault(sec, {"sector": sec, "bull": 0.0, "bear": 0.0, "n": 0,
                                 "names": []})
        a["n"] += 1
        if d == "bullish":
            a["bull"] += r["conviction"]
        elif d == "bearish":
            a["bear"] += r["conviction"]
        a["names"].append(r["symbol"])
    out = []
    for a in agg.values():
        if a["n"] < 2 or a["sector"] == "Other":
            continue
        tot = a["bull"] + a["bear"]
        net = round((a["bull"] - a["bear"]) / tot * 100, 1) if tot else 0.0
        out.append({
            "sector": a["sector"], "count": a["n"], "net_bias": net,
            "direction": ("bullish" if net > 15 else "bearish" if net < -15 else "mixed"),
            "names": a["names"][:6],
        })
    out.sort(key=lambda x: abs(x["net_bias"]), reverse=True)
    return out


def _market_bias(rows, index_matrix):
    """Conviction-weighted long vs short pressure, overlaid with index PCR."""
    bull = bear = 0.0
    for r in rows:
        meta = BUILDUP_META[r["buildup"]]
        w = r["conviction"] * (1.0 if meta["strong"] else 0.5)
        if meta["dir"] == "bullish":
            bull += w
        elif meta["dir"] == "bearish":
            bear += w
    tot = bull + bear
    score = round((bull - bear) / tot * 100, 1) if tot else 0.0

    # Nudge with NIFTY PCR if present (gentle ±8 overlay)
    nifty = next((i for i in index_matrix if i["symbol"] == "NIFTY"), None)
    if nifty and nifty.get("pcr") is not None:
        p = nifty["pcr"]
        if p >= PCR_BULL_STRONG:
            score += 8
        elif p >= PCR_BULL:
            score += 4
        elif p <= PCR_BEAR_STRONG:
            score -= 8
        elif p <= PCR_BEAR:
            score -= 4
    score = round(_clamp(score, -100.0, 100.0), 1)
    label = ("BULLISH" if score >= BULLISH_BIAS_CUT
             else "BEARISH" if score <= BEARISH_BIAS_CUT else "NEUTRAL")
    return {"score": score, "label": label,
            "bull_pressure": round(bull, 0), "bear_pressure": round(bear, 0)}


def _pcr_word(p):
    if p is None:
        return "n/a"
    if p >= PCR_BULL_STRONG:
        return "heavy put-writing (bullish)"
    if p >= PCR_BULL:
        return "put-heavy (mildly bullish)"
    if p <= PCR_BEAR_STRONG:
        return "heavy call-writing (bearish)"
    if p <= PCR_BEAR:
        return "call-heavy (mildly bearish)"
    return "balanced"


def _narrative(bias, buildups, index_matrix, sectors, unusual):
    """Deterministic English institutional read (no LLM)."""
    parts = []
    nlong = len(buildups["LONG_BUILDUP"])
    nshort = len(buildups["SHORT_BUILDUP"])
    nsc = len(buildups["SHORT_COVERING"])
    nlu = len(buildups["LONG_UNWINDING"])
    lab = bias["label"].capitalize()
    parts.append(
        f"Derivatives desk reads {lab.upper()} (bias {bias['score']:+.0f}). "
        f"{nlong} names with fresh long buildup and {nsc} short-covering vs "
        f"{nshort} short buildup and {nlu} long-unwinding."
    )
    top = None
    for cat in ("LONG_BUILDUP", "SHORT_BUILDUP", "SHORT_COVERING", "LONG_UNWINDING"):
        if buildups[cat]:
            cand = buildups[cat][0]
            if top is None or cand["conviction"] > top["conviction"]:
                top = cand
    if top:
        parts.append(
            f"Highest-conviction footprint: {top['symbol']} "
            f"({BUILDUP_META[top['buildup']]['label']}, OI {top['oi_chg_pct']:+.1f}%, "
            f"price {top['px_chg_pct']:+.1f}%, conviction {top['conviction']})."
        )
    nifty = next((i for i in index_matrix if i["symbol"] == "NIFTY"), None)
    if nifty:
        mp = f"max-pain {int(nifty['max_pain'])}" if nifty.get("max_pain") else "max-pain n/a"
        parts.append(f"Nifty PCR {nifty.get('pcr')} — {_pcr_word(nifty.get('pcr'))}; {mp}.")
    if sectors:
        s = sectors[0]
        if s["direction"] != "mixed":
            parts.append(
                f"Clustered {s['direction']} positioning in {s['sector']} "
                f"({s['count']} names)."
            )
    if unusual:
        u = unusual[0]
        parts.append(
            f"Largest OI surge: {u['symbol']} ({u['oi_chg_pct']:+.0f}% OI, "
            f"{u['buildup_label'].lower()})."
        )
    return " ".join(parts)


def build_smart_money_board(snapshot, watchlist=None, delivery=None, deals=None):
    """
    Assemble the full F&O Smart-Money board from a raw bhavcopy snapshot.

    snapshot : {"bhavcopy_date","fetched_at","futures":{...},"options":{...}}
               (from marketdata.oi_data.get_fno_raw_snapshot)
    watchlist: optional list of tickers to flag/highlight.
    delivery : optional {SYM: deliv_pct} from the cash bhavdata (for conviction
               + the delivery-spike table).
    deals    : optional list of bulk/block deal dicts (passed straight through).

    Returns a JSON-safe board dict. Never raises.
    """
    snapshot = snapshot or {}
    futures = snapshot.get("futures") or {}
    options = snapshot.get("options") or {}
    delivery = {normalize_ticker(k): v for k, v in (delivery or {}).items()}
    watchset = {normalize_ticker(t) for t in (watchlist or [])}

    rows = []
    for sym, fut in futures.items():
        sym = normalize_ticker(sym)
        if not sym:
            continue
        opt_entry = options.get(sym) or {}
        deliv = delivery.get(sym)
        rows.append(_build_row(sym, fut, opt_entry, deliv, watchset))

    # Buildup tables (drop thin, ranked by conviction)
    buildups = {k: [] for k in
                ("LONG_BUILDUP", "SHORT_BUILDUP", "SHORT_COVERING", "LONG_UNWINDING")}
    for r in rows:
        if r["buildup"] in buildups and r["val_cr"] >= MIN_VAL_CR:
            buildups[r["buildup"]].append(r)
    for k in buildups:
        buildups[k].sort(key=lambda x: x["conviction"], reverse=True)
        buildups[k] = buildups[k][:MAX_LIST]

    # Unusual OI surges
    unusual = [r for r in rows
               if abs(r["oi_chg_pct"]) >= UNUSUAL_OI_PCT and r["val_cr"] >= MIN_VAL_CR
               and r["buildup"] != "NEUTRAL"]
    unusual.sort(key=lambda x: abs(x["oi_chg_pct"]), reverse=True)
    unusual = unusual[:MAX_UNUSUAL]

    # Delivery spikes (high delivery % = genuine accumulation, not intraday churn)
    deliv_rows = [r for r in rows if r["delivery_pct"] is not None and r["delivery_pct"] >= 55]
    deliv_rows.sort(key=lambda x: x["delivery_pct"], reverse=True)
    deliv_rows = deliv_rows[:MAX_DELIVERY]

    index_matrix = _index_matrix(options)
    sectors = _sector_clustering(rows)
    bias = _market_bias(rows, index_matrix)
    narrative = _narrative(bias, buildups, index_matrix, sectors, unusual)

    # Watchlist slice (the user's names that appear in F&O today)
    watch_rows = [r for r in rows if r["in_watchlist"]]
    watch_rows.sort(key=lambda x: x["conviction"], reverse=True)

    counts = {BUILDUP_META[k]["label"]: len([r for r in rows if r["buildup"] == k])
              for k in BUILDUP_META}

    return {
        "bhavcopy_date": snapshot.get("bhavcopy_date"),
        "fetched_at": snapshot.get("fetched_at"),
        "age_seconds": snapshot.get("age_seconds"),
        "universe_count": len(rows),
        "market_bias": bias,
        "narrative": narrative,
        "counts": counts,
        "index_matrix": index_matrix,
        "buildups": buildups,
        "unusual_oi": unusual,
        "delivery_spikes": deliv_rows,
        "sectors": sectors,
        "deals": (deals or [])[:30],
        "watchlist": watch_rows,
        "applicable": bool(rows),
    }
