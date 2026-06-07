"""
F&O data fetcher — NSE daily derivatives bhavcopy parser.

Downloads the daily NSE F&O bhavcopy ONCE (cached for 4 hours) and parses it
into TWO things:

  1. Per-stock FUTURES OI + price-change snapshot  → OI-buildup pattern
     (the original purpose; feeds the TechnicalAlignmentModel).
  2. Per-symbol OPTIONS chain (CE/PE OI by strike, OI change, spot)
     → powers the F&O Smart-Money board (PCR, max-pain, OI walls).

Both come from the SAME already-downloaded file, so the richer options data
costs ZERO extra network calls.

Bhavcopy format (NSE UDiFF, 2024+):
  URL: https://archives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_<YYYYMMDD>_F_0000.csv.zip
  Published ~7-8 PM IST on every trading day.
  FinInstrmTp:  STF (stock future) · STO (stock option)
                IDF (index future) · IDO (index option)
  Key cols:     TckrSymb, OptnTp(CE/PE), StrkPric, XpryDt, OpnIntrst,
                ChngInOpnIntrst, ClsPric, PrvsClsgPric, UndrlygPric,
                TtlTradgVol, TtlTrfVal

Futures buildup patterns (front-month):
  LONG_BUILDUP   — price up + OI up   (institutional longs adding)
  SHORT_COVERING — price up + OI down (forced buying, weaker)
  SHORT_BUILDUP  — price down + OI up (institutional shorts adding)
  LONG_UNWINDING — price down + OI down (profit-taking, weaker)
  NEUTRAL        — tiny price move
  NOT_FNO        — stock isn't in F&O segment
  UNKNOWN        — bhavcopy fetch failed (network/NSE-side)

NOTE on reachability: this hits archives.nseindia.com — the STATIC archive CDN,
which is a different host from the datacenter-IP-blocked api.nseindia.com. The
archive CDN has historically been reachable from the server, but the live record
parse should still be validated in production (see /api/debug-worker-status and
the [OI]/[FNO] worker logs). Every public function is failure-tolerant.

Thread-safe (singleton cache + lock), failure-tolerant, bandwidth-friendly (one
fetch / 4h serves the entire process).
"""
import csv as _csv
import io
import threading
import zipfile
from datetime import datetime, timedelta, timezone

import requests


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

_IST = timezone(timedelta(hours=5, minutes=30))
_CACHE_TTL_HOURS = 4

# Module-level cache. Keys:
#   "futures": dict[str, dict] — symbol -> futures summary
#   "options": dict[str, dict] — symbol -> {expiry, spot, is_index, strikes[]}
#   "date": date object — which trading day's bhavcopy this is from
#   "fetched_at": datetime UTC — when we put this in cache
_CACHE: dict = {"futures": None, "options": None, "date": None, "fetched_at": None}
_CACHE_LOCK = threading.Lock()


def _ist_now() -> datetime:
    return datetime.now(_IST)


def _last_likely_bhavcopy_date():
    """The most recent trading day for which the bhavcopy is likely published.

    NSE publishes daily F&O bhavcopy around 7-8 PM IST. Before that, we have
    to use yesterday's file. Rolls back through Sat/Sun automatically; we'll
    further fall back through the most recent N days if the chosen date 404s.
    """
    now = _ist_now()
    d = now.date()
    if now.hour < 19:
        d -= timedelta(days=1)
    while d.weekday() >= 5:  # Saturday=5, Sunday=6
        d -= timedelta(days=1)
    return d


def _fetch_bhavcopy(date_obj):
    """GET the bhavcopy ZIP for `date_obj` (a date). Returns CSV text or None."""
    ymd = date_obj.strftime("%Y%m%d")
    url = (
        f"https://archives.nseindia.com/content/fo/"
        f"BhavCopy_NSE_FO_0_0_0_{ymd}_F_0000.csv.zip"
    )
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        if resp.status_code != 200 or len(resp.content) < 1000:
            return None
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        for name in zf.namelist():
            if name.lower().endswith(".csv"):
                return zf.read(name).decode("utf-8", errors="ignore")
    except Exception as exc:
        print(f"[OI] bhavcopy fetch failed for {date_obj}: {exc}")
    return None


def _f(row, key, default=0.0):
    """Tolerant float read from a (whitespace-stripped) row dict."""
    try:
        return float(row.get(key) or default)
    except (ValueError, TypeError):
        return default


def _i(row, key, default=0):
    try:
        return int(float(row.get(key) or default))
    except (ValueError, TypeError):
        return default


def _parse_bhavcopy_full(csv_text: str) -> dict:
    """Parse the bhavcopy CSV into per-stock FUTURES + per-symbol OPTIONS.

    Returns {"futures": {...}, "options": {...}}.

    futures[sym] = {oi_total, oi_chg_total, oi_chg_pct, px_chg_pct,
                    front_close, front_prev, front_xpry, vol, val_cr}
    options[sym] = {expiry, spot, is_index, ce_oi, pe_oi, ce_chg, pe_chg,
                    strikes: [{strike, ce_oi, pe_oi, ce_chg, pe_chg,
                               ce_vol, pe_vol}, ...]}
    """
    reader = _csv.DictReader(io.StringIO(csv_text))
    futures: dict[str, dict] = {}

    # options scratch: sym -> expiry -> strike -> cell
    opt_tmp: dict[str, dict] = {}
    opt_spot: dict[str, float] = {}
    opt_is_index: set = set()

    for raw in reader:
        # Normalize: strip whitespace from keys AND values (cash files have
        # leading-space headers; FO is clean but be defensive).
        row = {
            (k or "").strip(): (v.strip() if isinstance(v, str) else v)
            for k, v in raw.items()
        }
        fit = (row.get("FinInstrmTp") or "").strip().upper()
        sym = (row.get("TckrSymb") or "").strip().upper()
        if not sym:
            continue

        # ── FUTURES (stock) ──
        if fit == "STF":
            oi = _i(row, "OpnIntrst")
            oi_chg = _i(row, "ChngInOpnIntrst")
            cls_pric = _f(row, "ClsPric")
            prv_pric = _f(row, "PrvsClsgPric")
            vol = _i(row, "TtlTradgVol")
            val = _f(row, "TtlTrfVal")
            xpry = (row.get("XpryDt") or "").strip()

            entry = futures.get(sym)
            if entry is None:
                entry = {
                    "oi_total": 0, "oi_chg_total": 0,
                    "front_close": cls_pric, "front_prev": prv_pric,
                    "front_xpry": xpry, "vol": 0, "val": 0.0,
                }
                futures[sym] = entry

            entry["oi_total"] += oi
            entry["oi_chg_total"] += oi_chg
            entry["vol"] += vol
            entry["val"] += val
            # Track front (nearest) expiry for the price-change read
            if xpry and (not entry["front_xpry"] or xpry < entry["front_xpry"]):
                entry["front_close"] = cls_pric
                entry["front_prev"] = prv_pric
                entry["front_xpry"] = xpry

        # ── OPTIONS (stock + index) ──
        elif fit in ("STO", "IDO"):
            otp = (row.get("OptnTp") or "").strip().upper()
            if otp not in ("CE", "PE"):
                continue
            strike = _f(row, "StrkPric")
            xpry = (row.get("XpryDt") or "").strip()
            if strike <= 0 or not xpry:
                continue
            oi = _i(row, "OpnIntrst")
            oi_chg = _i(row, "ChngInOpnIntrst")
            vol = _i(row, "TtlTradgVol")
            spot = _f(row, "UndrlygPric")

            cell = (
                opt_tmp.setdefault(sym, {})
                       .setdefault(xpry, {})
                       .setdefault(strike, {
                           "ce_oi": 0, "pe_oi": 0, "ce_chg": 0,
                           "pe_chg": 0, "ce_vol": 0, "pe_vol": 0,
                       })
            )
            if otp == "CE":
                cell["ce_oi"] += oi
                cell["ce_chg"] += oi_chg
                cell["ce_vol"] += vol
            else:
                cell["pe_oi"] += oi
                cell["pe_chg"] += oi_chg
                cell["pe_vol"] += vol
            if spot > 0:
                opt_spot[sym] = spot
            if fit == "IDO":
                opt_is_index.add(sym)

    # Derive percent price change + OI change % per future
    for entry in futures.values():
        prv = entry["front_prev"]
        entry["px_chg_pct"] = (
            round((entry["front_close"] - prv) / prv * 100, 3) if prv > 0 else 0.0
        )
        prev_oi = entry["oi_total"] - entry["oi_chg_total"]
        entry["oi_chg_pct"] = (
            round(entry["oi_chg_total"] / prev_oi * 100, 2) if prev_oi > 0 else 0.0
        )
        entry["val_cr"] = round(entry.get("val", 0.0) / 1e7, 2)

    # Finalize options: keep only the FRONT (nearest) expiry per symbol.
    options: dict[str, dict] = {}
    for sym, by_exp in opt_tmp.items():
        if not by_exp:
            continue
        front = min(by_exp.keys())  # ISO date strings → lexicographic = chronological
        strikes_map = by_exp[front]
        strikes = []
        ce_oi = pe_oi = ce_chg = pe_chg = 0
        for k in sorted(strikes_map.keys()):
            c = strikes_map[k]
            strikes.append({
                "strike": round(k, 2),
                "ce_oi": c["ce_oi"], "pe_oi": c["pe_oi"],
                "ce_chg": c["ce_chg"], "pe_chg": c["pe_chg"],
                "ce_vol": c["ce_vol"], "pe_vol": c["pe_vol"],
            })
            ce_oi += c["ce_oi"]; pe_oi += c["pe_oi"]
            ce_chg += c["ce_chg"]; pe_chg += c["pe_chg"]
        options[sym] = {
            "expiry": front,
            "spot": round(opt_spot.get(sym, 0.0), 2),
            "is_index": sym in opt_is_index,
            "ce_oi": ce_oi, "pe_oi": pe_oi,
            "ce_chg": ce_chg, "pe_chg": pe_chg,
            "strikes": strikes,
        }

    return {"futures": futures, "options": options}


def _ensure_cache() -> dict:
    """Return {"futures":..., "options":...}, fetching if not cached or stale."""
    now_utc = datetime.now(timezone.utc)

    with _CACHE_LOCK:
        if _CACHE["futures"] is not None and _CACHE["fetched_at"] is not None:
            age_s = (now_utc - _CACHE["fetched_at"]).total_seconds()
            if age_s < _CACHE_TTL_HOURS * 3600:
                return {"futures": _CACHE["futures"], "options": _CACHE["options"]}

    # Try the last 7 candidate trading days in case of holidays / stale CDN
    target = _last_likely_bhavcopy_date()
    for back in range(7):
        d = target - timedelta(days=back)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        csv_text = _fetch_bhavcopy(d)
        if not csv_text:
            continue
        parsed = _parse_bhavcopy_full(csv_text)
        if parsed.get("futures") or parsed.get("options"):
            with _CACHE_LOCK:
                _CACHE["futures"] = parsed["futures"]
                _CACHE["options"] = parsed["options"]
                _CACHE["date"] = d
                _CACHE["fetched_at"] = now_utc
            print(
                f"[OI] Loaded F&O bhavcopy {d}: "
                f"{len(parsed['futures'])} futures, "
                f"{len(parsed['options'])} option symbols"
            )
            return {"futures": parsed["futures"], "options": parsed["options"]}

    # All candidates failed — cache a brief empty so we don't hammer NSE
    print("[OI] No bhavcopy reachable — OI/F&O features will return UNKNOWN/empty")
    with _CACHE_LOCK:
        _CACHE["futures"] = {}
        _CACHE["options"] = {}
        _CACHE["date"] = None
        _CACHE["fetched_at"] = now_utc
    return {"futures": {}, "options": {}}


# Tiny dead-zone so a 0.02% move isn't called "directional"
_PX_NEUTRAL_THRESHOLD = 0.05  # percent


def get_oi_buildup_for_ticker(ticker: str) -> str:
    """
    Returns one of:
      LONG_BUILDUP / SHORT_COVERING / SHORT_BUILDUP / LONG_UNWINDING
      NEUTRAL / NOT_FNO / UNKNOWN

    Safe — never raises. On any failure or unknown ticker, returns 'UNKNOWN' /
    'NOT_FNO', both of which the TechnicalAlignmentModel treats as neutral.
    """
    try:
        sym = (ticker or "").upper().replace(".NS", "").replace(".BO", "").strip()
        if not sym:
            return "UNKNOWN"

        snap = _ensure_cache()
        futures = snap.get("futures") or {}
        if not futures:
            return "UNKNOWN"

        entry = futures.get(sym)
        if not entry:
            # bhavcopy loaded fine but the symbol isn't there → not F&O
            return "NOT_FNO"

        px_chg = entry.get("px_chg_pct", 0.0)
        oi_chg = entry.get("oi_chg_total", 0)

        if abs(px_chg) < _PX_NEUTRAL_THRESHOLD:
            return "NEUTRAL"

        px_up = px_chg > 0
        oi_up = oi_chg > 0

        if px_up and oi_up:
            return "LONG_BUILDUP"
        if px_up and not oi_up:
            return "SHORT_COVERING"
        if not px_up and oi_up:
            return "SHORT_BUILDUP"
        return "LONG_UNWINDING"
    except Exception as exc:
        print(f"[OI] get_oi_buildup_for_ticker({ticker!r}) failed: {exc}")
        return "UNKNOWN"


def get_fno_raw_snapshot() -> dict:
    """
    Full F&O snapshot for the Smart-Money board.

    Returns:
      {
        "bhavcopy_date": "YYYY-MM-DD" | None,
        "fetched_at":    iso str | None,
        "age_seconds":   float | None,
        "futures":       {SYM: {...}},     # see _parse_bhavcopy_full
        "options":       {SYM: {...}},     # front-expiry chains (stocks + indices)
      }

    Never raises — returns empty maps on any failure.
    """
    try:
        snap = _ensure_cache()
    except Exception as exc:
        print(f"[FNO] get_fno_raw_snapshot failed: {exc}")
        snap = {"futures": {}, "options": {}}

    with _CACHE_LOCK:
        date = _CACHE.get("date")
        fetched = _CACHE.get("fetched_at")

    age = (datetime.now(timezone.utc) - fetched).total_seconds() if fetched else None
    return {
        "bhavcopy_date": (date.isoformat() if date else None),
        "fetched_at": (fetched.isoformat() if fetched else None),
        "age_seconds": age,
        "futures": snap.get("futures") or {},
        "options": snap.get("options") or {},
    }


def get_option_chain_raw(symbol: str) -> dict:
    """Front-expiry option chain (strike ladder) for one symbol, or {} if absent."""
    try:
        sym = (symbol or "").upper().replace(".NS", "").replace(".BO", "").strip()
        if not sym:
            return {}
        snap = _ensure_cache()
        return (snap.get("options") or {}).get(sym, {}) or {}
    except Exception as exc:
        print(f"[FNO] get_option_chain_raw({symbol!r}) failed: {exc}")
        return {}


def cache_status() -> dict:
    """Helpful introspection: how fresh is our F&O snapshot?"""
    with _CACHE_LOCK:
        fut = _CACHE.get("futures")
        opt = _CACHE.get("options")
        date = _CACHE.get("date")
        fetched = _CACHE.get("fetched_at")
    return {
        "futures_loaded": (len(fut) if isinstance(fut, dict) else 0),
        "option_symbols_loaded": (len(opt) if isinstance(opt, dict) else 0),
        "bhavcopy_date": (date.isoformat() if date else None),
        "fetched_at": (fetched.isoformat() if fetched else None),
        "age_seconds": (
            (datetime.now(timezone.utc) - fetched).total_seconds() if fetched else None
        ),
    }


# ════════════════════════════════════════════════════════════════════════════
# OPTIONAL SECONDARY SOURCES — delivery % + bulk/block deals
#
# Both hit the NSE equity archive CDN (different files from the FO bhavcopy).
# Each is fully ISOLATED: failure → {} / [] and a worker log line, never breaks
# the Smart-Money board (the board is built primarily on the FO bhavcopy above).
# ⚠️ Live-record reachability/format should be validated in PRODUCTION — the
# equity archive endpoints can behave differently from the FO archive host, and
# could not be exercised against live data in the build env. Watch the [FNO]
# logs + /api/debug-worker-status.
# ════════════════════════════════════════════════════════════════════════════
_ARCHIVE_HOSTS = ["https://nsearchives.nseindia.com", "https://archives.nseindia.com"]

_DELIV_CACHE: dict = {"data": None, "date": None, "fetched_at": None}
_DELIV_LOCK = threading.Lock()

_DEALS_CACHE: dict = {"data": None, "fetched_at": None}
_DEALS_LOCK = threading.Lock()


def _fetch_archive_csv(path: str, min_bytes: int = 100):
    """GET a CSV from the NSE equity archive CDN (tries both hosts). Text or None."""
    for host in _ARCHIVE_HOSTS:
        try:
            resp = requests.get(host + path, headers=_HEADERS, timeout=20)
            if resp.status_code == 200 and len(resp.content) >= min_bytes:
                return resp.text
        except Exception as exc:
            print(f"[FNO] archive fetch failed {host}{path}: {exc}")
    return None


def get_delivery_map() -> dict:
    """
    {SYMBOL: delivery_pct} from the latest NSE cash bhavdata (EQ series).

    High delivery % = buyers taking delivery (genuine accumulation) vs intraday
    churn — a classic smart-money confirmation. Cached 4h. {} on any failure.
    """
    now_utc = datetime.now(timezone.utc)
    with _DELIV_LOCK:
        if _DELIV_CACHE["data"] is not None and _DELIV_CACHE["fetched_at"] is not None:
            if (now_utc - _DELIV_CACHE["fetched_at"]).total_seconds() < _CACHE_TTL_HOURS * 3600:
                return _DELIV_CACHE["data"]

    target = _last_likely_bhavcopy_date()
    for back in range(7):
        d = target - timedelta(days=back)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        path = f"/products/content/sec_bhavdata_full_{d.strftime('%d%m%Y')}.csv"
        txt = _fetch_archive_csv(path, min_bytes=1000)
        if not txt:
            continue
        out: dict = {}
        try:
            reader = _csv.DictReader(io.StringIO(txt))
            for raw in reader:
                row = {(k or "").strip(): (v.strip() if isinstance(v, str) else v)
                       for k, v in raw.items()}
                if (row.get("SERIES") or "").upper() != "EQ":
                    continue
                sym = (row.get("SYMBOL") or "").upper().strip()
                if not sym:
                    continue
                try:
                    dp = float(row.get("DELIV_PER") or 0)
                except (ValueError, TypeError):
                    continue   # "-" for non-deliverable rows
                if dp > 0:
                    out[sym] = round(dp, 2)
        except Exception as exc:
            print(f"[FNO] delivery parse failed: {exc}")
            continue
        if out:
            with _DELIV_LOCK:
                _DELIV_CACHE.update({"data": out, "date": d, "fetched_at": now_utc})
            print(f"[FNO] Loaded delivery% for {len(out)} stocks (bhavdata {d})")
            return out

    with _DELIV_LOCK:
        _DELIV_CACHE.update({"data": {}, "date": None, "fetched_at": now_utc})
    return {}


def _parse_deals(txt: str, kind: str) -> list:
    """Parse a bulk/block deals CSV into normalized dicts. Tolerant of headers."""
    out = []
    try:
        reader = _csv.DictReader(io.StringIO(txt))
        for raw in reader:
            row = {(k or "").strip(): (v.strip() if isinstance(v, str) else v)
                   for k, v in raw.items()}
            sym = (row.get("Symbol") or row.get("SYMBOL") or "").upper().strip()
            if not sym:
                continue
            client = (row.get("Client Name") or row.get("CLIENT NAME")
                      or row.get("Name of Client") or "").strip()
            side = (row.get("Buy/Sell") or row.get("BUY/SELL") or "").upper().strip()
            qty = (row.get("Quantity Traded") or row.get("QUANTITY TRADED")
                   or row.get("Quantity") or "").strip()
            price = (row.get("Trade Price / Wght. Avg. Price")
                     or row.get("Trade Price/Wght.Avg.Price")
                     or row.get("TRADE PRICE / WGHT. AVG. PRICE")
                     or row.get("Price") or "").strip()
            date = (row.get("Date") or row.get("DATE") or "").strip()
            out.append({
                "symbol": sym,
                "client": client[:60],
                "side": ("BUY" if side.startswith("B")
                         else "SELL" if side.startswith("S") else side),
                "qty": qty,
                "price": price,
                "date": date,
                "kind": kind,
            })
    except Exception as exc:
        print(f"[FNO] deals parse failed ({kind}): {exc}")
    return out


def get_bulk_block_deals() -> list:
    """
    Latest NSE bulk + block deals — direct institutional footprints.

    bulk.csv / block.csv carry the most recent session's deals. Cached 4h.
    Returns a capped list of normalized deal dicts; [] on any failure.
    """
    now_utc = datetime.now(timezone.utc)
    with _DEALS_LOCK:
        if _DEALS_CACHE["data"] is not None and _DEALS_CACHE["fetched_at"] is not None:
            if (now_utc - _DEALS_CACHE["fetched_at"]).total_seconds() < _CACHE_TTL_HOURS * 3600:
                return _DEALS_CACHE["data"]

    deals: list = []
    bulk = _fetch_archive_csv("/content/equities/bulk.csv")
    if bulk:
        deals += _parse_deals(bulk, "bulk")
    block = _fetch_archive_csv("/content/equities/block.csv")
    if block:
        deals += _parse_deals(block, "block")

    deals = deals[:60]
    with _DEALS_LOCK:
        _DEALS_CACHE.update({"data": deals, "fetched_at": now_utc})
    if deals:
        print(f"[FNO] Loaded {len(deals)} bulk/block deals")
    return deals
