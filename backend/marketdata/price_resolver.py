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
