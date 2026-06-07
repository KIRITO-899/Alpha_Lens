"""
ripple_engine.py — Ripple 2.0: a deterministic, quantitative macro-shock
propagation engine.

Given a macro instrument shock (e.g. "Brent +4.2%"), this produces a five-
dimension cascade the way a sell-side quant desk would frame it:

    1. DIRECT IMPACT      — names whose P&L is mechanically tied to the move
    2. SECOND-ORDER IMPACT — supply-chain / input-cost / financing transmission
    3. SECTOR IMPACT      — the stock-level moves rolled up to sector net bias
    4. PORTFOLIO IMPACT   — how the shock hits THIS user's watchlist (exposure)
    5. ACTION WINDOW      — when it's tradable (pre-open vs live) + horizon + urgency

WHY DETERMINISTIC (no LLM):
    Each stock carries a *signed beta* — its expected % move per +1% move in the
    macro instrument — grounded in the transmission mechanism (margin, input cost,
    duration, risk-on/off). Expected move = beta x shock%, saturating at a cap.
    This is reproducible, unit-testable, instant, burns zero API keys, and never
    hallucinates a ticker — the opposite of the old Gemini ripple. The betas are
    seeded from the institutional correlations already encoded in
    app.compute_macro_effects() and refined per name.

Pure module: stdlib only, no app/network/DB imports -> no import cycle. app.py
imports compute_ripple() and calls it from the /ripple2 route.
"""
from __future__ import annotations

# ── Tunables (module constants; kept here so the engine stays pure) ──
MAX_EXPECTED_MOVE = 6.0     # cap |expected stock move| from a single shock (%)
MAX_DIRECT_NODES  = 6       # show at most this many direct names
MAX_SECOND_NODES  = 6       # show at most this many second-order names
CONF_DIRECT_BASE  = 82      # base confidence for a direct-impact node
CONF_SECOND_BASE  = 66      # base confidence for a second-order node
CONF_FLOOR        = 50
CONF_CEIL         = 95

# A transmission node = (ticker, display_name, sector, beta, lag, mechanism)
#   beta : signed expected stock %-move per +1% move of the instrument.
#          Positive beta => stock rises when the instrument rises.
#          The engine flips it automatically for a down-move (expected = beta*pct).
#   lag  : 'immediate' (intraday repricing) | 'lagged' (1-3 sessions to flow through)
#
# Instruments are grouped: brent/wti share the oil graph, gold/silver the
# precious graph, etc. KEY_TO_GROUP maps the 13 tracked instruments onto 8 graphs.

_GROUPS = {
    # ─────────────────────────── CRUDE OIL ───────────────────────────
    'oil': {
        'narrative': 'crude oil',
        'direct': [
            ('ONGC.NS', 'ONGC', 'Energy — Upstream', +0.85, 'immediate',
             'Higher crude lifts upstream realizations and net margins'),
            ('OIL.NS', 'Oil India', 'Energy — Upstream', +0.90, 'immediate',
             'Realization-led upstream margin expansion'),
            ('BPCL.NS', 'BPCL', 'Energy — OMC', -0.55, 'immediate',
             'Costlier crude squeezes refining & marketing margins'),
            ('IOC.NS', 'Indian Oil', 'Energy — OMC', -0.50, 'immediate',
             'OMC marketing margins compress as input crude rises'),
            ('HINDPETRO.NS', 'HPCL', 'Energy — OMC', -0.50, 'immediate',
             'Refining/marketing margin pressure on higher crude'),
        ],
        'second': [
            ('INDIGO.NS', 'InterGlobe Aviation', 'Aviation', -0.95, 'immediate',
             'ATF (jet fuel) is ~35% of airline opex; crude up inflates the fuel bill'),
            ('ASIANPAINT.NS', 'Asian Paints', 'Paints & Chemicals', -0.55, 'lagged',
             'Crude-derived inputs (monomers, solvents) raise COGS with a lag'),
            ('BERGEPAINT.NS', 'Berger Paints', 'Paints & Chemicals', -0.50, 'lagged',
             'Crude-linked raw-material cost pressure'),
            ('SRF.NS', 'SRF', 'Chemicals', -0.35, 'lagged',
             'Petrochem feedstock cost tracks crude higher'),
        ],
    },
    # ─────────────────────────── NATURAL GAS ─────────────────────────
    'gas': {
        'narrative': 'natural gas',
        'direct': [
            ('ONGC.NS', 'ONGC', 'Energy — Upstream', +0.30, 'immediate',
             'Higher gas realizations on domestic output'),
            ('GAIL.NS', 'GAIL', 'Gas — Transmission', +0.20, 'lagged',
             'Petchem spread and transmission economics shift with gas'),
        ],
        'second': [
            ('IGL.NS', 'Indraprastha Gas', 'Gas — Distribution', -0.30, 'lagged',
             'Higher LNG sourcing cost squeezes city-gas margins'),
            ('MGL.NS', 'Mahanagar Gas', 'Gas — Distribution', -0.32, 'lagged',
             'Input gas cost pressure compresses CGD margins'),
            ('GUJGASLTD.NS', 'Gujarat Gas', 'Gas — Distribution', -0.30, 'lagged',
             'Industrial volume + margin risk on costlier gas'),
        ],
    },
    # ─────────────────────────── PRECIOUS ────────────────────────────
    'precious': {
        'narrative': 'precious metals',
        'direct': [
            ('MUTHOOTFIN.NS', 'Muthoot Finance', 'Gold Financier', +0.65, 'immediate',
             'Higher gold lifts collateral value and AUM headroom'),
            ('MANAPPURAM.NS', 'Manappuram', 'Gold Financier', +0.60, 'immediate',
             'Gold-loan collateral value rises'),
            ('TITAN.NS', 'Titan', 'Jewellery & Retail', +0.45, 'immediate',
             'Jewellery inventory revaluation gains (partly offset by demand)'),
            ('KALYANKJIL.NS', 'Kalyan Jewellers', 'Jewellery & Retail', +0.55, 'immediate',
             'Inventory value gains on rising gold'),
        ],
        'second': [],
    },
    # ─────────────────────────── BASE METALS (Copper) ────────────────
    'metals': {
        'narrative': 'base metals',
        'direct': [
            ('HINDCOPPER.NS', 'Hindustan Copper', 'Metals', +0.70, 'immediate',
             'Direct copper producer — full leverage to LME price'),
            ('VEDL.NS', 'Vedanta', 'Metals', +0.55, 'immediate',
             'Diversified base-metal realizations rise'),
            ('HINDALCO.NS', 'Hindalco', 'Metals', +0.50, 'immediate',
             'LME-linked aluminium/copper realizations improve'),
            ('NATIONALUM.NS', 'NALCO', 'Metals', +0.45, 'immediate',
             'Base-metal price tailwind to realizations'),
        ],
        'second': [
            ('HAVELLS.NS', 'Havells', 'Electricals', -0.35, 'lagged',
             'Copper is a key input — cable/wire COGS rises'),
            ('POLYCAB.NS', 'Polycab', 'Electricals', -0.40, 'lagged',
             'Copper feedstock cost pressure on cables'),
        ],
    },
    # ─────────────────────────── USD / INR ───────────────────────────
    # A +1% move = stronger USD / weaker INR (DXY up, or USDINR up).
    'usd': {
        'narrative': 'a stronger dollar / weaker rupee',
        'direct': [
            ('INFY.NS', 'Infosys', 'IT Services', +1.40, 'immediate',
             'Weaker INR inflates USD-revenue translation'),
            ('TCS.NS', 'TCS', 'IT Services', +1.20, 'immediate',
             'Currency tailwind to USD billings'),
            ('HCLTECH.NS', 'HCL Tech', 'IT Services', +1.20, 'immediate',
             'Export-led revenue benefits from weaker INR'),
            ('SUNPHARMA.NS', 'Sun Pharma', 'Pharma', +0.80, 'immediate',
             'US generics revenue translation benefit'),
        ],
        'second': [
            ('BPCL.NS', 'BPCL', 'Energy — OMC', -0.60, 'lagged',
             'Costlier crude imports in INR terms widen under-recovery risk'),
            ('MARUTI.NS', 'Maruti Suzuki', 'Auto', -0.50, 'lagged',
             'Imported components/royalty in foreign currency raise costs'),
        ],
    },
    # ─────────────────────────── VOLATILITY (VIX) ────────────────────
    # A +1% move = rising volatility = risk-off.
    'vol': {
        'narrative': 'a volatility spike (risk-off)',
        'direct': [
            ('ICICIBANK.NS', 'ICICI Bank', 'Banks — Private', -0.20, 'immediate',
             'FII risk-off outflows hit high-weight private banks first'),
            ('HDFCBANK.NS', 'HDFC Bank', 'Banks — Private', -0.18, 'immediate',
             'Index-heavy financials lead drawdowns in risk-off'),
            ('DLF.NS', 'DLF', 'Realty', -0.25, 'immediate',
             'High-beta cyclicals sold hardest when vol spikes'),
            ('RELIANCE.NS', 'Reliance', 'Large Cap', -0.15, 'immediate',
             'Index heavyweight de-risking'),
        ],
        'second': [
            ('ITC.NS', 'ITC', 'FMCG', +0.10, 'immediate',
             'Defensive low-beta rotation cushions / lifts staples'),
            ('HINDUNILVR.NS', 'Hindustan Unilever', 'FMCG', +0.08, 'immediate',
             'Flight to defensive staples'),
        ],
    },
    # ─────────────────────────── EQUITY INDEX ────────────────────────
    'index': {
        'narrative': 'the equity index',
        'direct': [
            ('ICICIBANK.NS', 'ICICI Bank', 'Banks — Private', +1.00, 'immediate',
             'High index weight tracks the benchmark move'),
            ('HDFCBANK.NS', 'HDFC Bank', 'Banks — Private', +0.90, 'immediate',
             'Heavyweight financial moves with the index'),
            ('RELIANCE.NS', 'Reliance', 'Large Cap', +0.80, 'immediate',
             'Largest index weight matches the move'),
            ('INFY.NS', 'Infosys', 'IT Services', +0.85, 'immediate',
             'Index-weight tracking'),
        ],
        'second': [
            ('DLF.NS', 'DLF', 'Realty', +1.30, 'immediate',
             'High-beta cyclical amplifies the index move'),
            ('TATAMOTORS.NS', 'Tata Motors', 'Auto', +1.20, 'immediate',
             'High-beta name amplifies the benchmark direction'),
        ],
    },
    # ─────────────────────────── RATES (US 10Y) ──────────────────────
    # A +1% move = higher US yields.
    'rates': {
        'narrative': 'higher US yields',
        'direct': [
            ('TCS.NS', 'TCS', 'IT Services', -0.15, 'lagged',
             'Higher discount rate compresses long-duration / DCF valuations'),
            ('INFY.NS', 'Infosys', 'IT Services', -0.15, 'lagged',
             'Rate-sensitive growth multiple de-rates'),
        ],
        'second': [
            ('DLF.NS', 'DLF', 'Realty', -0.25, 'lagged',
             'Higher borrowing cost pressures realty demand and financing'),
            ('LT.NS', 'Larsen & Toubro', 'Infra & Capex', -0.15, 'lagged',
             'Leveraged capex cycle faces a financing-cost headwind'),
            ('HDFCBANK.NS', 'HDFC Bank', 'Banks — Private', -0.12, 'lagged',
             'Bond-book MTM and NIM uncertainty on a yield spike'),
        ],
    },
}

# 13 tracked instruments -> 8 transmission graphs
KEY_TO_GROUP = {
    'brent': 'oil', 'wti': 'oil',
    'natgas': 'gas',
    'gold': 'precious', 'silver': 'precious',
    'copper': 'metals',
    'dxy': 'usd', 'usdinr': 'usd',
    'vix_us': 'vol', 'vix_in': 'vol',
    'nifty': 'index', 'banknifty': 'index',
    'us10y': 'rates',
}


# ───────────────────────────── helpers ──────────────────────────────
def normalize_ticker(t):
    """'tcs', 'TCS.NS', 'TCS.BO' -> 'TCS' for watchlist matching."""
    s = str(t or '').upper().strip()
    for suf in ('.NS', '.BO'):
        if s.endswith(suf):
            s = s[:-len(suf)]
    return s


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _expected_move(beta, pct):
    """Signed expected stock move = beta x shock%, saturating at the cap."""
    raw = beta * pct
    return round(_clamp(raw, -MAX_EXPECTED_MOVE, MAX_EXPECTED_MOVE), 2)


def _confidence(order, beta, shock_level):
    """Deterministic confidence: base by order, + severity, + |beta| conviction."""
    base = CONF_DIRECT_BASE if order == 1 else CONF_SECOND_BASE
    sev = {'MAJOR': 8, 'SIGNIFICANT': 3}.get((shock_level or '').upper(), 0)
    conv = 3 if abs(beta) >= 0.8 else (1 if abs(beta) >= 0.4 else 0)
    return int(_clamp(base + sev + conv, CONF_FLOOR, CONF_CEIL))


def _node(raw, order, pct, shock_level):
    ticker, name, sector, beta, lag, mech = raw
    move = _expected_move(beta, pct)
    if move == 0:
        return None
    return {
        'ticker': ticker,
        'name': name,
        'sector': sector,
        'order': order,
        'direction': 'BULLISH' if move > 0 else 'BEARISH',
        'expected_move_pct': move,
        'beta': beta,
        'lag': lag,
        'confidence': _confidence(order, beta, shock_level),
        'mechanism': mech,
    }


def _sector_rollup(nodes):
    """Aggregate stock moves into a per-sector net bias, sorted by |net|."""
    buckets = {}
    for n in nodes:
        b = buckets.setdefault(n['sector'], {'sector': n['sector'], 'moves': [], 'tickers': []})
        b['moves'].append(n['expected_move_pct'])
        b['tickers'].append({'ticker': n['ticker'], 'name': n['name'],
                             'expected_move_pct': n['expected_move_pct']})
    out = []
    for b in buckets.values():
        net = round(sum(b['moves']) / len(b['moves']), 2)
        top = sorted(b['tickers'], key=lambda t: -abs(t['expected_move_pct']))[:3]
        out.append({
            'sector': b['sector'],
            'net_move_pct': net,
            'direction': 'BULLISH' if net > 0 else ('BEARISH' if net < 0 else 'NEUTRAL'),
            'count': len(b['moves']),
            'top': top,
        })
    out.sort(key=lambda s: -abs(s['net_move_pct']))
    return out


def _portfolio_impact(all_nodes, watchlist):
    """How the shock lands on the user's watchlist (equal-weight exposure math)."""
    wl = [normalize_ticker(t) for t in (watchlist or []) if str(t or '').strip()]
    wl_set = set(wl)
    if not wl_set:
        return {'applicable': False,
                'summary': 'Add stocks to your watchlist to see portfolio impact.'}

    # Best (most extreme) node per watchlist ticker — a name can appear in both
    # direct and second-order; keep the larger-magnitude hit.
    hits = {}
    for n in all_nodes:
        key = normalize_ticker(n['ticker'])
        if key not in wl_set:
            continue
        if key not in hits or abs(n['expected_move_pct']) > abs(hits[key]['expected_move_pct']):
            hits[key] = n

    hit_list = sorted(hits.values(), key=lambda n: -abs(n['expected_move_pct']))
    exposure = len(hit_list)
    total = len(wl_set)
    if exposure == 0:
        return {'applicable': True, 'exposure_count': 0, 'total': total,
                'net_move_pct': 0.0, 'direction': 'NEUTRAL', 'hits': [],
                'summary': f'None of your {total} watchlist name'
                           f'{"s" if total != 1 else ""} are directly in this '
                           f'shock’s transmission path.'}

    net = round(sum(h['expected_move_pct'] for h in hit_list) / exposure, 2)
    direction = 'BULLISH' if net > 0 else ('BEARISH' if net < 0 else 'NEUTRAL')
    bull = sum(1 for h in hit_list if h['expected_move_pct'] > 0)
    bear = exposure - bull
    return {
        'applicable': True,
        'exposure_count': exposure,
        'total': total,
        'net_move_pct': net,
        'direction': direction,
        'hits': hit_list,
        'summary': f'{exposure} of {total} watchlist names exposed '
                   f'({bull} bullish / {bear} bearish) — est. equal-weight '
                   f'impact {("+" if net >= 0 else "")}{net}%.',
    }


def _action_window(shock_level, during_nse_hours, nodes):
    """When is this tradable, over what horizon, how urgent."""
    lvl = (shock_level or '').upper()
    urgency = {'MAJOR': 'HIGH', 'SIGNIFICANT': 'MEDIUM'}.get(lvl, 'LOW')

    lagged = sum(1 for n in nodes if n['lag'] == 'lagged')
    immediate = len(nodes) - lagged
    horizon = '1–3 sessions' if lagged > immediate else 'Intraday → 1 session'

    if during_nse_hours == 0:
        state, label = 'ACTIONABLE', 'Actionable before open'
        detail = ('Shock landed while NSE was shut — names are not yet repriced. '
                  'A position can be taken before the 9:15 IST open.')
    elif during_nse_hours == 1:
        state, label = 'LIVE', 'Repricing live'
        detail = ('NSE is open — the affected names are already repricing. '
                  'Chase with discipline; the edge decays fast.')
    else:
        state, label = 'INFO', 'Monitor'
        detail = 'Session timing unknown — treat as informational and confirm on the tape.'

    return {
        'state': state,
        'label': label,
        'horizon': horizon,
        'urgency': urgency,
        'during_nse_hours': during_nse_hours,
        'detail': detail,
    }


def _summary(label, pct, shock_level, direct, second, sectors):
    sign = '+' if pct >= 0 else ''
    nodes = direct + second
    bull = sum(1 for n in nodes if n['expected_move_pct'] > 0)
    bear = len(nodes) - bull
    lead = ''
    if nodes:
        strongest = max(nodes, key=lambda n: abs(n['expected_move_pct']))
        s_sign = '+' if strongest['expected_move_pct'] >= 0 else ''
        lead = (f" Strongest read: {strongest['name']} "
                f"{s_sign}{strongest['expected_move_pct']}%.")
    sv = f"{shock_level.title()} " if shock_level else ''
    return (f"{label} {sign}{pct}% ({sv}shock) propagates to {bull} bullish / "
            f"{bear} bearish names across {len(sectors)} sector"
            f"{'s' if len(sectors) != 1 else ''}.{lead}")


# ───────────────────────────── entry point ──────────────────────────
def compute_ripple(instrument_key, pct, shock_level=None,
                   during_nse_hours=None, watchlist=None, instrument_label=None):
    """
    Build the full five-dimension Ripple 2.0 for a macro shock.

    Args:
        instrument_key : one of MacroDataTracker.INSTRUMENTS keys (e.g. 'brent')
        pct            : signed 1-day % move of the instrument
        shock_level    : 'MAJOR' | 'SIGNIFICANT' | None (drives confidence/urgency)
        during_nse_hours: 1 if detected while NSE open, 0 if shut, None if unknown
        watchlist      : list of tickers (any format) for the portfolio dimension
        instrument_label: human label (e.g. 'Brent Crude'); falls back to the key

    Returns a JSON-serializable dict (never raises for known inputs; an unknown
    instrument yields an empty-but-valid shell).
    """
    try:
        pct = round(float(pct), 2)
    except (TypeError, ValueError):
        pct = 0.0
    label = instrument_label or str(instrument_key or 'Macro event').title()
    group_key = KEY_TO_GROUP.get(str(instrument_key or '').lower())
    group = _GROUPS.get(group_key)

    if not group or pct == 0.0:
        return {
            'instrument_key': instrument_key,
            'instrument': label,
            'pct': pct,
            'shock_level': shock_level,
            'summary': f'{label} {("+" if pct >= 0 else "")}{pct}% — no '
                       f'mapped transmission path.',
            'direct': [], 'second_order': [], 'sector': [],
            'portfolio': _portfolio_impact([], watchlist),
            'action_window': _action_window(shock_level, during_nse_hours, []),
        }

    direct = [n for n in (_node(r, 1, pct, shock_level) for r in group['direct']) if n]
    second = [n for n in (_node(r, 2, pct, shock_level) for r in group['second']) if n]

    # Rank by conviction-weighted magnitude, then cap each tier.
    direct.sort(key=lambda n: -(abs(n['expected_move_pct']) * n['confidence']))
    second.sort(key=lambda n: -(abs(n['expected_move_pct']) * n['confidence']))
    direct = direct[:MAX_DIRECT_NODES]
    second = second[:MAX_SECOND_NODES]

    all_nodes = direct + second
    sectors = _sector_rollup(all_nodes)

    return {
        'instrument_key': instrument_key,
        'instrument': label,
        'pct': pct,
        'shock_level': shock_level,
        'summary': _summary(label, pct, shock_level, direct, second, sectors),
        'direct': direct,
        'second_order': second,
        'sector': sectors,
        'portfolio': _portfolio_impact(all_nodes, watchlist),
        'action_window': _action_window(shock_level, during_nse_hours, all_nodes),
    }
