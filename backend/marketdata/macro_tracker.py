"""
MacroDataTracker — live commodity / FX / rates snapshot via Yahoo Finance's
free public chart endpoint (Brent, WTI, Gold, DXY, USD/INR, VIX, Nifty, US10Y,
...). Extracted verbatim from app.py.

Self-contained: stdlib (time, threading, concurrent.futures) + its own requests
session, with all caching held at class level (cls._cache, 5-min TTL). No app
import -> no cycle. app.py imports the class back and calls it class-level
(MacroDataTracker.get_snapshot() / .detect_shocks()).
"""
import os
import time
import threading
import statistics
import concurrent.futures
import requests

# Dedicated session (app.py keeps its own HTTP_SESSION for other callers).
HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})


def _envf(name, default):
    """Float env reader that never raises (falls back to default)."""
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


# ── Pure volatility helpers (no network/state -> unit-testable) ──────────
def daily_returns(closes):
    """A list of daily closes (Nones tolerated) -> list of daily % returns."""
    out = []
    prev = None
    for c in closes or []:
        if c is None:
            continue
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        if prev is not None and prev != 0:
            out.append((c / prev - 1.0) * 100.0)
        prev = c
    return out


def compute_vol_stats(returns, change_pct_1d, window=60):
    """
    Quant core: turn a move into a volatility-normalized z-score (σ).

    Args:
        returns        : historical daily % returns EXCLUDING today's move
                         (so the move never inflates its own vol estimate).
        change_pct_1d  : today's signed % move.
        window         : trailing sample size for the realized-vol estimate.

    Returns dict(vol_pct, sigma, pctile, sample):
        vol_pct : realized daily volatility (sample std of returns, %)
        sigma   : signed z-score = change_pct_1d / vol_pct  (None if no vol)
        pctile  : percentile rank of |move| within |historical returns| (0-100)
        sample  : number of returns used
    Degrades gracefully: sample < 5 or zero-vol -> sigma/pctile = None.
    """
    rs = [r for r in (returns or []) if r is not None]
    sample = rs[-int(window):] if window and len(rs) > int(window) else rs
    n = len(sample)
    if n < 5:
        return {'vol_pct': None, 'sigma': None, 'pctile': None, 'sample': n}
    try:
        vol = statistics.stdev(sample)
    except statistics.StatisticsError:
        return {'vol_pct': None, 'sigma': None, 'pctile': None, 'sample': n}
    if vol <= 1e-9:
        return {'vol_pct': round(vol, 4), 'sigma': None, 'pctile': None, 'sample': n}
    try:
        sigma = round(float(change_pct_1d) / vol, 2)
    except (TypeError, ValueError):
        sigma = None
    mag = abs(float(change_pct_1d)) if change_pct_1d is not None else 0.0
    le = sum(1 for r in sample if abs(r) <= mag)
    pctile = round(le / n * 100.0, 1)
    return {'vol_pct': round(vol, 4), 'sigma': sigma, 'pctile': pctile, 'sample': n}


class MacroDataTracker:
    INSTRUMENTS = {
        'brent':     {'symbol': 'BZ=F',      'label': 'Brent Crude'},
        'wti':       {'symbol': 'CL=F',      'label': 'WTI Crude'},
        'natgas':    {'symbol': 'NG=F',      'label': 'Natural Gas'},
        'gold':      {'symbol': 'GC=F',      'label': 'Gold'},
        'silver':    {'symbol': 'SI=F',      'label': 'Silver'},
        'copper':    {'symbol': 'HG=F',      'label': 'Copper'},
        'dxy':       {'symbol': 'DX-Y.NYB',  'label': 'Dollar Index'},
        'usdinr':    {'symbol': 'INR=X',     'label': 'USD/INR'},
        'vix_us':    {'symbol': '^VIX',      'label': 'US VIX'},
        'vix_in':    {'symbol': '^INDIAVIX', 'label': 'India VIX'},
        'nifty':     {'symbol': '^NSEI',     'label': 'Nifty 50'},
        'banknifty': {'symbol': '^NSEBANK',  'label': 'Bank Nifty'},
        'us10y':     {'symbol': '^TNX',      'label': 'US 10Y Yield'},
    }

    # Per-instrument shock thresholds (% absolute 1-day move). These are
    # calibrated to "rare enough that it matters" for each asset class.
    # When the actual % move >= the MAJOR threshold, the macro detector
    # flags a "MAJOR" event. When it's between SIGNIFICANT and MAJOR, it's
    # a "SIGNIFICANT" event. Below SIGNIFICANT = ignore.
    # No keyword matching — purely quantitative on real prices.
    SHOCK_THRESHOLDS = {
        # Commodities — high baseline vol → tighter thresholds need 3-5%
        'brent':     {'significant': 3.0, 'major': 5.0},
        'wti':       {'significant': 3.0, 'major': 5.0},
        'natgas':    {'significant': 4.0, 'major': 7.0},
        'gold':      {'significant': 1.5, 'major': 3.0},
        'silver':    {'significant': 2.5, 'major': 5.0},
        'copper':    {'significant': 2.0, 'major': 4.0},
        # FX — low daily vol → tighter cutoffs
        'dxy':       {'significant': 0.8, 'major': 1.5},
        'usdinr':    {'significant': 0.5, 'major': 1.0},
        # Vol indices — usually move a lot when they move
        'vix_us':    {'significant': 12.0, 'major': 20.0},
        'vix_in':    {'significant': 10.0, 'major': 18.0},
        # Equity indices
        'nifty':     {'significant': 1.5, 'major': 2.5},
        'banknifty': {'significant': 1.8, 'major': 3.0},
        # Rates
        'us10y':     {'significant': 5.0, 'major': 8.0},
    }

    # ── σ-based (volatility-normalized) shock detection ──
    # A move's significance is its z-score = |return| / realized daily vol, which
    # is comparable across assets and across vol regimes — unlike a fixed %. One
    # σ threshold is correct for every instrument. SHOCK_THRESHOLDS (above) is the
    # automatic fallback when there isn't enough history to estimate vol.
    SHOCK_MODE        = os.getenv('MACRO_SHOCK_MODE', 'sigma').lower()  # 'sigma' | 'pct'
    SIGMA_SIGNIFICANT = _envf('MACRO_SIGMA_SIGNIFICANT', 2.5)
    SIGMA_MAJOR       = _envf('MACRO_SIGMA_MAJOR', 3.5)
    VOL_WINDOW        = int(_envf('MACRO_VOL_WINDOW', 60))   # trailing days for vol
    ABS_FLOOR_PCT     = _envf('MACRO_ABS_FLOOR_PCT', 0.1)    # ignore sub-floor noise
    HISTORY_RANGE     = os.getenv('MACRO_HISTORY_RANGE', '6mo')

    _cache = {}
    _cache_time = 0.0
    _CACHE_TTL = 300  # 5 minutes
    _lock = threading.Lock()

    @classmethod
    def _fetch_one(cls, key, meta):
        """
        Single instrument fetch via Yahoo's free chart endpoint. Pulls ~6mo of
        daily closes so we can compute realized volatility and a z-score (σ) for
        today's move, not just the raw %.
        """
        try:
            url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
                   f"{meta['symbol']}?range={cls.HISTORY_RANGE}&interval=1d")
            resp = HTTP_SESSION.get(url, timeout=6)
            if resp.status_code != 200:
                return None
            data = resp.json()
            result = (data.get('chart') or {}).get('result') or [{}]
            res0 = result[0] or {}
            meta_data = res0.get('meta') or {}
            # Daily close series (also used for realized-vol / σ below).
            closes = (((res0.get('indicators') or {}).get('quote') or [{}])[0] or {}).get('close') or []

            # Live price with a robust fallback: Yahoo sometimes omits
            # regularMarketPrice for Indian indices (^NSEI) — fall back to the
            # most recent valid close so the value is never blank/stale-null.
            last = meta_data.get('regularMarketPrice')
            if last is None:
                for c in reversed(closes):
                    if c is not None:
                        last = c
                        break
            prev = meta_data.get('chartPreviousClose') or meta_data.get('previousClose')
            if prev is None:
                valid = [c for c in closes if c is not None]
                if len(valid) >= 2:
                    prev = valid[-2]   # prior session's close as the reference
            if last is None or prev is None or float(prev) == 0:
                return None
            last_f = float(last); prev_f = float(prev)
            pct = (last_f - prev_f) / prev_f * 100.0

            # Realized-vol / σ from the daily close series. Exclude the most
            # recent return so today's move doesn't inflate its own vol estimate.
            rets = daily_returns(closes)
            hist = rets[:-1] if len(rets) >= 2 else rets
            vs = compute_vol_stats(hist, pct, cls.VOL_WINDOW)

            return {
                'key':            key,
                'symbol':         meta['symbol'],
                'label':          meta['label'],
                'last':           round(last_f, 4),
                'prev_close':     round(prev_f, 4),
                'change_pct_1d':  round(pct, 2),
                'is_shock_3pct':  abs(pct) >= 3.0,
                'is_shock_5pct':  abs(pct) >= 5.0,
                'vol_pct':        vs['vol_pct'],
                'sigma':          vs['sigma'],
                'pctile':         vs['pctile'],
                'sample':         vs['sample'],
            }
        except Exception:
            return None

    @classmethod
    def get_snapshot(cls):
        now = time.time()
        with cls._lock:
            if cls._cache and (now - cls._cache_time) < cls._CACHE_TTL:
                return cls._cache
        # Parallel fetch — 13 small HTTP calls. 4 workers keeps memory low
        # while still being ~3x faster than serial.
        snap = {}
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures = {pool.submit(cls._fetch_one, k, m): k
                           for k, m in cls.INSTRUMENTS.items()}
                for fut in concurrent.futures.as_completed(futures, timeout=15):
                    try:
                        result = fut.result(timeout=1)
                        if result:
                            snap[result['key']] = result
                    except Exception:
                        pass
        except Exception:
            pass
        with cls._lock:
            cls._cache = snap
            cls._cache_time = now
        return snap

    @classmethod
    def classify_shock(cls, instrument):
        """
        Classify a snapshot row's move as ('MAJOR'/'SIGNIFICANT'/None, threshold).

        Primary path (SHOCK_MODE='sigma'): volatility-normalized — the move's
        z-score (|return| / realized daily vol) is compared against ONE σ
        threshold that holds for every asset class. A small absolute floor
        (ABS_FLOOR_PCT) suppresses statistically-large-but-economically-trivial
        moves in ultra-low-vol instruments.

        Fallback path (no σ available, or SHOCK_MODE='pct'): the original
        per-instrument fixed-% SHOCK_THRESHOLDS.

        Returns the triggering threshold as the 2nd element (σ in sigma-mode,
        % in pct-mode) for context.
        """
        if not instrument or instrument.get('change_pct_1d') is None:
            return (None, None)
        move = abs(instrument['change_pct_1d'])
        sigma = instrument.get('sigma')

        if cls.SHOCK_MODE == 'sigma' and sigma is not None:
            if move < cls.ABS_FLOOR_PCT:
                return (None, None)
            asig = abs(sigma)
            if asig >= cls.SIGMA_MAJOR:
                return ('MAJOR', cls.SIGMA_MAJOR)
            if asig >= cls.SIGMA_SIGNIFICANT:
                return ('SIGNIFICANT', cls.SIGMA_SIGNIFICANT)
            return (None, None)

        # Fallback: per-instrument fixed-% thresholds.
        thr = cls.SHOCK_THRESHOLDS.get(instrument.get('key'))
        if not thr:
            return (None, None)
        if move >= thr['major']:
            return ('MAJOR', thr['major'])
        if move >= thr['significant']:
            return ('SIGNIFICANT', thr['significant'])
        return (None, None)

    @classmethod
    def detect_shocks(cls):
        """
        Return current snapshot enriched with shock classification.
        Each item gets a `shock_level` field: 'MAJOR' / 'SIGNIFICANT' / None.
        Only items where level != None are returned, sorted by severity.
        """
        snap = cls.get_snapshot()
        out = []
        for inst in snap.values():
            level, threshold = cls.classify_shock(inst)
            if not level:
                continue
            row = dict(inst)
            row['shock_level'] = level
            row['threshold_pct'] = threshold
            out.append(row)
        # MAJOR first, then SIGNIFICANT; within each, biggest σ-move first
        # (falls back to raw % when σ is unavailable).
        out.sort(key=lambda r: (0 if r['shock_level'] == 'MAJOR' else 1,
                                -abs(r.get('sigma') if r.get('sigma') is not None
                                     else r['change_pct_1d'])))
        return out
