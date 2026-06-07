"""
nifty_outlook.py — Nifty Next-Session Outlook: a deterministic, transparent
pre-open bias model.

Aggregates the live macro board (overnight global cues already tracked by
MacroDataTracker) into an expected NIFTY next-session **directional bias** +
**expected % range** + **honest confidence** + a fully transparent per-driver
contribution breakdown.

⚠️ HONESTY CONTRACT: this is a *bias estimate* — the framework a macro desk uses
pre-open ("crude soft, dollar firm, US vol up → cautious open") — NOT a prediction
guarantee. Markets gap on news, earnings and flows this model cannot see. The model
therefore caps its own confidence (never > 80), shows every input that drove the
read, and labels itself a bias, not a forecast of fact.

WHY DETERMINISTIC (no LLM): each macro driver carries a *signed beta* — the expected
NIFTY %-move per +1% move of that driver — grounded in India's macro structure
(net oil importer, EM beta to the dollar and US rates, risk-on/off via volatility).
NIFTY expected move = Σ(driver_change × beta), each term and the total saturated at
a cap. Reproducible, unit-testable, instant, zero API keys.

Pure module: stdlib only, no app/network/DB imports → no cycle. app.py imports
compute_nifty_outlook() and calls it from /api/macro/nifty-outlook.
"""
from __future__ import annotations

# NIFTY sensitivity to each macro driver — expected NIFTY %-move per +1% move of
# the driver, SIGNED. Grounded in India macro structure; these are directional
# sensitivities for a *bias*, not precise regression coefficients.
#
# Only non-redundant drivers are included: brent (not wti — same oil signal),
# gold (not silver — same precious signal); banknifty/nifty themselves are NOT
# drivers of the NIFTY read (they ARE the index), and natgas is too NIFTY-neutral
# to add signal.
DRIVERS = {
    'vix_us': {'beta': -0.045, 'label': 'US VIX',
               'why': 'Global risk-off → FII de-risking of EM equities'},
    'dxy':    {'beta': -0.40,  'label': 'Dollar Index',
               'why': 'A stronger dollar pulls flows out of India/EM'},
    'us10y':  {'beta': -0.06,  'label': 'US 10Y Yield',
               'why': 'Higher US yields pressure EM valuations & flows'},
    'brent':  {'beta': -0.09,  'label': 'Brent Crude',
               'why': 'India is a net oil importer (CAD / inflation drag)'},
    'usdinr': {'beta': -0.22,  'label': 'USD/INR',
               'why': 'A weaker rupee is an FII-outflow drag (IT partly offsets)'},
    'gold':   {'beta': -0.03,  'label': 'Gold',
               'why': 'A safe-haven bid signals risk caution'},
    'copper': {'beta': +0.05,  'label': 'Copper',
               'why': 'A global growth / risk-on proxy'},
    'vix_in': {'beta': -0.03,  'label': 'India VIX',
               'why': 'Domestic risk gauge'},
}

MAX_CONTRIB    = 1.20   # cap any single driver's contribution to NIFTY (%)
MAX_EXPECTED   = 3.00   # cap the aggregate expected NIFTY move (%)
DEFAULT_RANGE  = 0.80   # fallback ± range (%) if NIFTY realized vol is unavailable
CONF_FLOOR     = 25
CONF_CEIL      = 80     # honest ceiling — never claim near-certainty on a forecast


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_nifty_outlook(snapshot, during_nse_hours=None):
    """
    Build the Nifty Next-Session Outlook from a MacroDataTracker snapshot.

    Args:
        snapshot         : {key: {change_pct_1d, last, vol_pct, sigma, ...}} dict.
        during_nse_hours : 1 if NSE is open (intraday read), 0 if shut (next-session
                           pre-open read), None if unknown.

    Returns a JSON-safe dict (never raises). `applicable=False` when no driver
    data is present.
    """
    snapshot = snapshot or {}
    nifty = snapshot.get('nifty') or {}

    contributions = []
    total = 0.0
    for key, d in DRIVERS.items():
        inst = snapshot.get(key)
        if not inst:
            continue
        chg = _f(inst.get('change_pct_1d'))
        if chg is None:
            continue
        contrib = round(_clamp(d['beta'] * chg, -MAX_CONTRIB, MAX_CONTRIB), 3)
        if contrib == 0.0:
            continue
        contributions.append({
            'key': key,
            'label': d['label'],
            'change_pct': round(chg, 2),
            'beta': d['beta'],
            'contribution_pct': contrib,
            'direction': 'BULLISH' if contrib > 0 else 'BEARISH',
            'why': d['why'],
        })
        total += contrib

    expected = round(_clamp(total, -MAX_EXPECTED, MAX_EXPECTED), 2)
    contributions.sort(key=lambda c: -abs(c['contribution_pct']))

    # Probability-banded range from NIFTY's own realized daily vol (1σ). The most
    # likely next-session outcome is the macro bias ± one daily σ (≈68% of days
    # under a normal random-walk approx); ±2σ bounds the ≈95% "all possibilities"
    # range. (vol_pct is the genuine realized daily vol — computed from true daily
    # returns — so it stays correct independent of the 1-day-change fix.)
    vol = _f(nifty.get('vol_pct'))
    band = round(vol, 2) if vol and vol > 0 else DEFAULT_RANGE
    range_low = round(expected - band, 2)
    range_high = round(expected + band, 2)
    wide = round(band * 2, 2)
    wide_low = round(expected - wide, 2)
    wide_high = round(expected + wide, 2)

    # Confidence: honest, capped. Built from driver AGREEMENT (do the cues align?),
    # breadth (how many cues), and magnitude — never near-certainty.
    sum_abs = sum(abs(c['contribution_pct']) for c in contributions)
    agreement = round(abs(total) / sum_abs, 2) if sum_abs > 0 else 0.0  # 0..1
    n = len(contributions)
    conf = (35
            + agreement * 30
            + min(n, 8) / 8.0 * 10
            + min(abs(expected), 1.5) / 1.5 * 10)
    confidence = int(_clamp(round(conf), CONF_FLOOR, CONF_CEIL))

    # Stance banding.
    if abs(expected) < 0.25:
        stance, stance_label = 'NEUTRAL', 'Flat / range-bound'
    elif expected >= 0.75:
        stance, stance_label = 'BULLISH', 'Positive bias'
    elif expected > 0:
        stance, stance_label = 'MILD_BULLISH', 'Mildly positive'
    elif expected <= -0.75:
        stance, stance_label = 'BEARISH', 'Risk-off bias'
    else:
        stance, stance_label = 'MILD_BEARISH', 'Mildly negative'

    # Horizon framing (intraday vs next-session pre-open).
    if during_nse_hours == 0:
        horizon, horizon_note = 'Next session', 'Pre-open read — NSE is shut'
    elif during_nse_hours == 1:
        horizon, horizon_note = 'Rest of session', 'Intraday — NSE is open'
    else:
        horizon, horizon_note = 'Next session', 'Pre-open read'

    # NIFTY reference + projected levels (most-likely 68% band + 95% outer bound).
    last = _f(nifty.get('last'))
    proj = round(last * (1 + expected / 100.0), 2) if last else None
    proj_low = round(last * (1 + range_low / 100.0), 2) if last else None
    proj_high = round(last * (1 + range_high / 100.0), 2) if last else None
    proj_wlow = round(last * (1 + wide_low / 100.0), 2) if last else None
    proj_whigh = round(last * (1 + wide_high / 100.0), 2) if last else None

    bull = sum(1 for c in contributions if c['contribution_pct'] > 0)
    bear = sum(1 for c in contributions if c['contribution_pct'] < 0)

    sign = '+' if expected >= 0 else ''
    if contributions:
        lead = contributions[0]
        lead_txt = (f" Strongest cue: {lead['label']} "
                    f"({'+' if lead['contribution_pct'] >= 0 else ''}"
                    f"{lead['contribution_pct']}% to NIFTY).")
        summary = (f"Overnight macro cues point to a {stance_label.lower()} NIFTY "
                   f"{horizon.lower()}: est. {sign}{expected}% "
                   f"(~68% range {range_low}% to {range_high}%; ~95% {wide_low}% to "
                   f"{wide_high}%), {confidence}% conviction. "
                   f"{bull} cue{'s' if bull != 1 else ''} bullish / "
                   f"{bear} bearish.{lead_txt}")
    else:
        summary = ('No macro driver data available right now — the next-session '
                   'outlook will populate once the global board loads.')

    return {
        'applicable': bool(contributions),
        'horizon': horizon,
        'horizon_note': horizon_note,
        'during_nse_hours': during_nse_hours,
        'nifty_last': last,
        'nifty_vol_pct': vol,
        'stance': stance,
        'stance_label': stance_label,
        'expected_move_pct': expected,
        'range_low_pct': range_low,
        'range_high_pct': range_high,
        'range_prob': 68,            # ≈ probability the close lands in [low, high] (±1σ)
        'daily_vol_pct': band,       # NIFTY realized daily σ used for the band
        'wide_low_pct': wide_low,    # ≈95% bound (±2σ) — "all possibilities"
        'wide_high_pct': wide_high,
        'projected_level': proj,
        'projected_low': proj_low,
        'projected_high': proj_high,
        'projected_wide_low': proj_wlow,
        'projected_wide_high': proj_whigh,
        'confidence': confidence,
        'agreement': agreement,
        'driver_count': n,
        'bull': bull,
        'bear': bear,
        'drivers': contributions,
        'summary': summary,
        'disclaimer': ('Directional bias from macro cues — not a guarantee. Markets '
                       'can gap on news, earnings and flows this model does not see.'),
    }
