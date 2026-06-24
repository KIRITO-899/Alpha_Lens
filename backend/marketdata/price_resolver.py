"""
Pure price-resolution helpers (no I/O, no app/network/DB imports).

The two functions here encode the *rules* that decide a stock's authoritative
prices, kept pure so they are unit-tested and reused identically by every code
path that needs a price.  All network/Yahoo/Angel plumbing lives in app.py; this
module only does the deterministic arithmetic/selection on already-fetched data.

WHY this exists — the "stale close" bug
---------------------------------------
Yahoo's daily-candle series (interval=1d) does NOT finalize *today's* bar until
some time after the 15:30 IST close — right after the bell the last daily bar
often has ``close == None``.  So a "last completed close" derived purely from the
daily series LAGS one full session: e.g. IOC showed 138.26 (Friday's close) when
the real Monday close was 135.6.  Meanwhile Yahoo's ``regularMarketPrice`` (with
``regularMarketTime`` stamped at ~15:30:01) already carries the genuine latest
close.  Different code paths picked different sources, so the same stock showed
different prices across the UI.  ``select_fresh_close`` reconciles the two into a
single, always-fresh answer.
"""

from datetime import date as _date, datetime as _datetime, timezone as _timezone
from email.utils import parsedate_to_datetime as _parsedate


def parse_timestamp(value):
    """Normalize a stored ``created_at`` into a tz-aware UTC datetime.

    Handles BOTH representations the app sees:
      * a **datetime object** — Postgres ``TIMESTAMP`` columns come back as
        (naive, UTC) datetimes via psycopg2;
      * a **string** — SQLite stores the RFC-1123 form
        ``'Mon, 08 Jun 2026 04:01:39 GMT'`` or an ISO / ``'YYYY-MM-DD HH:MM:SS'``.

    Returns None if unparseable. This single helper is why signal resolution and
    recompute behave identically on SQLite (local) and Postgres (prod) — the old
    string-only parser silently returned None for every Postgres row, so aged
    signals never resolved and recompute updated 0 rows.
    """
    if isinstance(value, _datetime):
        return value if value.tzinfo else value.replace(tzinfo=_timezone.utc)
    if value is None:
        return None
    try:
        s = str(value)
        if '+' in s or 'GMT' in s or ',' in s:
            dt = _parsedate(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=_timezone.utc)
        dt = _datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        return dt.replace(tzinfo=_timezone.utc)
    except Exception:
        try:
            dt = _datetime.fromisoformat(str(value))
            return dt if dt.tzinfo else dt.replace(tzinfo=_timezone.utc)
        except Exception:
            return None


def _round2(x):
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


def select_fresh_close(daily, reg_price=None, reg_time_ist=None):
    """Pick the most-recent COMPLETED session close + the prior session's close.

    Parameters
    ----------
    daily : list[(datetime.date, float)]
        Daily closes, ascending by date. May contain Nones/zeros (filtered out).
    reg_price : float | None
        Yahoo ``regularMarketPrice`` (the live/last-traded value).
    reg_time_ist : datetime | None
        IST-aware ``regularMarketTime``. Used to decide whether ``reg_price`` is a
        *completed-session* close (timestamp at/after 15:30 IST) and whether it is
        at least as fresh as the daily series.

    Returns
    -------
    (last_close, previous_close) : (float|None, float|None)

    Rule
    ----
    Use ``reg_price`` as the last close **iff** its timestamp is a completed NSE
    session (>= 15:30 IST) AND not older than the newest daily bar. That covers
    the "today's daily bar is still null right after the bell" lag without ever
    treating a mid-session live tick as a finished close (mid-session
    ``reg_time`` is < 15:30, so it falls through to the daily series). A
    ``reg_price`` stamped *older* than the daily series (a stale/again-quoted
    value) is ignored in favour of the daily bar.
    """
    clean = []
    for item in (daily or []):
        try:
            d, c = item
        except (TypeError, ValueError):
            continue
        cf = _round2(c)
        if cf and cf > 0 and isinstance(d, _date):
            clean.append((d, cf))
    clean.sort(key=lambda t: t[0])

    last_daily_date = clean[-1][0] if clean else None
    last_daily_close = clean[-1][1] if clean else None
    prior_daily_close = clean[-2][1] if len(clean) >= 2 else None

    rp = _round2(reg_price)
    use_rmp = False
    if rp and rp > 0 and reg_time_ist is not None:
        try:
            session_closed = (reg_time_ist.hour * 60 + reg_time_ist.minute) >= (15 * 60 + 30)
            fresh = (last_daily_date is None) or (reg_time_ist.date() >= last_daily_date)
            use_rmp = bool(session_closed and fresh)
        except (AttributeError, TypeError):
            use_rmp = False

    if use_rmp:
        rmp_date = reg_time_ist.date()
        if last_daily_date is not None and last_daily_date < rmp_date:
            # reg_price is a NEWER session than the daily series → the daily
            # series' last bar IS the previous close.
            prev = last_daily_close
        else:
            # reg_price is the same day the daily series already has → the prior
            # daily bar is the previous close.
            prev = prior_daily_close
        return rp, (prev if prev else None)

    if last_daily_close:
        return last_daily_close, (prior_daily_close if prior_daily_close else None)
    return None, None


def atr_stop_target(atr_pct,
                    stop_mult=0.5, target_mult=1.0,
                    fallback_stop_pct=1.0, fallback_target_pct=2.0,
                    stop_cap_pct=10.0, target_cap_pct=20.0):
    """Resolve (stop_pct, target_pct, used_atr) for a signal.

    Policy (per product spec):
      * ATR available  -> stop = ATR% * stop_mult (0.5 => ATR/2),
                          target = ATR% * target_mult (1.0 => ATR).
      * ATR missing/<=0 -> static fallback 1% stop / 2% target (NOT a skip).

    A wide sanity cap guards against a corrupt ATR (e.g. a data-glitch 80% ATR)
    producing an absurd stop/target; it is set high enough that it never binds
    for a real, liquid stock, so the ATR/2 & ATR relationship holds in practice.
    Returns (stop_pct, target_pct, used_atr: bool).
    """
    try:
        atr = float(atr_pct) if atr_pct is not None else 0.0
    except (TypeError, ValueError):
        atr = 0.0

    if atr > 0:
        stop = round(min(stop_cap_pct, atr * stop_mult), 2)
        target = round(min(target_cap_pct, atr * target_mult), 2)
        return stop, target, True

    return round(float(fallback_stop_pct), 2), round(float(fallback_target_pct), 2), False


def captured_atr(base_price, current_price, atr_pct, is_bullish):
    """How much of an ATR the stock has ALREADY moved IN THE SIGNAL'S FAVOUR
    between the news reference price (`base_price`) and now (`current_price`).

    Returns favourable ATRs captured:
      * > 0  -> the move is already underway (alpha decaying) — e.g. crude spikes,
               the OMC has already fallen, and we'd be shorting the exhaustion.
      * <= 0 -> the stock has NOT yet moved our way (a fresh entry), or has moved
               against the thesis (an even better entry).

    Pure / deterministic. FAIL-OPEN: returns 0.0 on any missing/zero/garbage
    input so a data hiccup can never *cause* a skip (the gate that consumes this
    only skips on a positive reading). Used by the "unreacted-move" entry gate
    (T1.2) and to tag the eval ledger (T0.4) so the threshold can be calibrated
    to realised outcomes instead of guessed.
    """
    try:
        bp = float(base_price) if base_price is not None else 0.0
        cp = float(current_price) if current_price is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
    if bp <= 0 or cp <= 0:
        return 0.0
    move_pct = (cp - bp) / bp * 100.0          # signed % move base->now
    fav_pct = move_pct if is_bullish else -move_pct
    try:
        a = float(atr_pct) if atr_pct is not None else 0.0
    except (TypeError, ValueError):
        a = 0.0
    if a <= 0:
        a = 0.5                                 # floor: avoid div-by-0 on no-ATR names
    return round(fav_pct / a, 3)


# ──────────────────────────────────────────────────────────────────────────
# TRADE EXIT SIMULATION — partial-profit + breakeven stop (pure, deterministic)
# ──────────────────────────────────────────────────────────────────────────
# WHY: a 0.5-ATR stop at 2:1 R:R needs only ~33% wins to break even, but a near-
# random entry still *reads* as a poor ~33% win-rate because every trade is all-or-
# nothing. The fix that raises the WIN-RATE **without widening the stop** is a
# smarter exit: book a partial at +1R and move the stop to BREAKEVEN. Then any
# trade that reaches +1R before the stop closes GREEN (partial locked, runner can
# only scratch or win), so the win-rate jumps from ~P(reach +2R) to ~P(reach +1R)
# — roughly 33% → ~50% for a symmetric path, honestly (it is realized P&L, not a
# relabel). This also fixes the old "both-touched candle = win" optimism by
# breaking ambiguous bars on the CLOSE direction.
#
# All math is in FAVORABLE %-from-entry space (positive = the trade went the way
# it was called), so longs and shorts share one code path — the caller converts
# its OHLC into favorable space with `to_favorable_bars` and flips the sign back.

def to_favorable_bars(ohlc_bars, base_price, is_bullish):
    """Convert absolute (open, high, low, close) bars → FAVORABLE %-from-entry bars.

    For a bullish call, favorable = price up, so high stays the favorable extreme.
    For a bearish call, favorable = price down, so the bar's LOW becomes the
    favorable high and vice-versa (signs flipped). Any field may be None.
    Returns list of (o, h, l, c) in favorable %; None fields pass through.
    """
    try:
        bp = float(base_price)
    except (TypeError, ValueError):
        return []
    if bp <= 0:
        return []

    def pct(x):
        if x is None:
            return None
        try:
            return (float(x) - bp) / bp * 100.0
        except (TypeError, ValueError):
            return None

    out = []
    for bar in (ohlc_bars or []):
        o, h, l, c = (tuple(bar) + (None, None, None, None))[:4]
        if is_bullish:
            out.append((pct(o), pct(h), pct(l), pct(c)))
        else:
            # favorable = down: best point is the low, worst is the high
            hp, lp, op, cp = pct(h), pct(l), pct(o), pct(c)
            out.append((
                (None if op is None else -op),
                (None if lp is None else -lp),   # favorable high  = -(price low%)
                (None if hp is None else -hp),   # favorable low   = -(price high%)
                (None if cp is None else -cp),
            ))
    return out


def simulate_exit(fav_bars, stop_pct, target_pct,
                  partial_enabled=True, partial_r=1.0, partial_frac=0.5,
                  cost_pct=0.0, expire_close_pct=None):
    """Simulate the partial-profit + breakeven-stop exit over favorable %-bars.

    Args
    ----
    fav_bars : list[(o, h, l, c)]  favorable %-from-entry bars, chronological.
    stop_pct, target_pct : positive % distances (target should be > partial dist).
    partial_enabled : book a partial at +partial_r·R and move stop to breakeven.
    partial_r : partial level in R (R = stop_pct). 1.0 ⇒ partial at +1R.
    partial_frac : fraction closed at the partial (0..1).
    cost_pct : round-trip transaction-cost % subtracted once on full close.
    expire_close_pct : if given, force-close any remainder at this favorable % when
        the bars run out (the time-stop exit); else leave the runner open.

    Returns dict: {resolved, status, pnl_pct, partial_done, remaining}
      status ∈ {'Predicted Target Hit','Stop Loss Hit','Breakeven Exit','Expired',None}
      pnl_pct : blended realized FAVORABLE % net of cost (+ = win), or None if
                nothing is realized yet (still fully open).
    """
    try:
        stop_pct = abs(float(stop_pct))
        target_pct = abs(float(target_pct))
        cost = abs(float(cost_pct or 0.0))
    except (TypeError, ValueError):
        return {'resolved': False, 'status': None, 'pnl_pct': None,
                'partial_done': False, 'remaining': 1.0}

    partial_dist = stop_pct * float(partial_r or 1.0)
    use_partial = (bool(partial_enabled) and 0.0 < float(partial_frac) < 1.0
                   and 0.0 < partial_dist < target_pct)
    pfrac = float(partial_frac) if use_partial else 0.0

    state = {'realized': 0.0, 'remaining': 1.0, 'partial_done': False,
             'cur_stop': -stop_pct}

    def _finalize(status, add_pnl):
        state['realized'] += add_pnl
        state['remaining'] = 0.0
        return {'resolved': True, 'status': status,
                'pnl_pct': round(state['realized'] - cost, 4),
                'partial_done': state['partial_done'], 'remaining': 0.0}

    def _book_partial(level):
        state['realized'] += pfrac * level
        state['remaining'] -= pfrac
        state['partial_done'] = True
        state['cur_stop'] = 0.0   # breakeven

    for bar in fav_bars:
        o, h, l, c = (tuple(bar) + (None, None, None, None))[:4]
        up_close = (c is not None and o is not None and c >= o)
        was_partial = state['partial_done']   # partial done BEFORE this bar?

        if not state['partial_done']:
            # ── Stage A: pre-partial. Gap at the open first (worst/best fills) ──
            if o is not None and o <= state['cur_stop']:
                return _finalize('Stop Loss Hit', state['remaining'] * o)
            if o is not None and o >= target_pct:
                # gapped through the full target → partial + runner both at open
                return _finalize('Predicted Target Hit', state['remaining'] * o)
            if use_partial and o is not None and o >= partial_dist:
                _book_partial(o)        # gapped through partial only; runner → next bar
            # ── intrabar touches (only if still pre-partial) ──
            if not state['partial_done']:
                hit_stop = (l is not None and l <= state['cur_stop'])
                hit_target = (h is not None and h >= target_pct)
                hit_partial = (use_partial and h is not None and h >= partial_dist)
                if hit_stop and (hit_target or hit_partial):
                    if not up_close:                 # close down ⇒ stop tagged first
                        return _finalize('Stop Loss Hit', state['remaining'] * state['cur_stop'])
                    if hit_target:                   # close up ⇒ favorable side first
                        if use_partial:
                            return _finalize('Predicted Target Hit',
                                             pfrac * partial_dist + (state['remaining'] - pfrac) * target_pct)
                        return _finalize('Predicted Target Hit', state['remaining'] * target_pct)
                    _book_partial(partial_dist)      # partial first, runner → next bar
                elif hit_stop:
                    return _finalize('Stop Loss Hit', state['remaining'] * state['cur_stop'])
                elif hit_target:
                    if use_partial:
                        return _finalize('Predicted Target Hit',
                                         pfrac * partial_dist + (state['remaining'] - pfrac) * target_pct)
                    return _finalize('Predicted Target Hit', state['remaining'] * target_pct)
                elif hit_partial:
                    _book_partial(partial_dist)
            continue   # whatever happened this bar, the runner resolves from NEXT bar

        # ── Stage B: runner open with stop at breakeven (0). Only reached on bars
        #    AFTER the partial bar (the `continue` above defers same-bar resolution),
        #    so open/high/low ordering is unambiguous. ──
        if was_partial and state['remaining'] > 1e-9:
            if o is not None and o <= 0.0:           # gap back to/below breakeven
                return _finalize('Breakeven Exit', state['remaining'] * o)
            if o is not None and o >= target_pct:    # gap through target
                return _finalize('Predicted Target Hit', state['remaining'] * o)
            hit_be = (l is not None and l <= 0.0)
            hit_target = (h is not None and h >= target_pct)
            if hit_be and hit_target:
                if up_close:
                    return _finalize('Predicted Target Hit', state['remaining'] * target_pct)
                return _finalize('Breakeven Exit', state['remaining'] * 0.0)
            elif hit_target:
                return _finalize('Predicted Target Hit', state['remaining'] * target_pct)
            elif hit_be:
                return _finalize('Breakeven Exit', state['remaining'] * 0.0)

    # ── bars exhausted ──
    if expire_close_pct is not None:
        try:
            state['realized'] += state['remaining'] * float(expire_close_pct)
        except (TypeError, ValueError):
            pass
        state['remaining'] = 0.0
        return {'resolved': True, 'status': 'Expired',
                'pnl_pct': round(state['realized'] - cost, 4),
                'partial_done': state['partial_done'], 'remaining': 0.0}
    return {'resolved': False, 'status': None,
            'pnl_pct': (round(state['realized'], 4) if state['partial_done'] else None),
            'partial_done': state['partial_done'],
            'remaining': round(state['remaining'], 4)}
