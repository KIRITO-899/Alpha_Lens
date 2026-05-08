"""
PERMANENT FIX: Restore correct base_price for all market-hours signals.

The bulk fix script wrongly set base_price = current_price for ALL active signals,
destroying the real intraday prices for signals created during market hours (9:15-15:30 IST).

This script:
1. Finds all active signals whose news_time was during market hours
2. Fetches the actual 1-min candle price at that time via Angel One API
3. Restores the correct base_price and recalculates estimated_change_percent
4. Leaves after-hours signals untouched (they correctly show 0%)
"""
import sys, io, os, sqlite3, time, json
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Angel One shim directly
import angelone_shim as ao

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_OPEN_H, MARKET_OPEN_M = 9, 15
MARKET_CLOSE_H, MARKET_CLOSE_M = 15, 30

def is_market_hours(dt_ist):
    """Returns True if datetime (IST) is within trading hours Mon-Fri."""
    if dt_ist.weekday() >= 5:
        return False
    t = dt_ist.hour * 60 + dt_ist.minute
    return (MARKET_OPEN_H * 60 + MARKET_OPEN_M) <= t <= (MARKET_CLOSE_H * 60 + MARKET_CLOSE_M)

def get_price_at_time_angelone(ticker, target_dt_ist):
    """
    Fetch stock price at target_dt_ist using Angel One 1-min candles.
    Returns the closest candle close price at or just before target_dt_ist.
    """
    exchange, token = ao._get_exchange_token(ticker)
    if not exchange or not token:
        print(f"    [!] No Angel One token for {ticker}")
        return None

    try:
        # Fetch 1-min candles for the day of the news (±2 hours around news time)
        from_dt = target_dt_ist - timedelta(hours=2)
        to_dt = target_dt_ist + timedelta(minutes=5)  # slight buffer

        df = ao._ao_get_candle(exchange, token, 'ONE_MINUTE', from_dt, to_dt)
        if df.empty:
            print(f"    [!] Empty 1-min data from Angel One for {ticker}")
            return None

        # Convert index to IST
        df.index = df.index.tz_convert(IST)

        # Find bars at or before target time
        past = df[df.index <= target_dt_ist]
        if past.empty:
            # Try any bar within 10 min after (in case of slight delay)
            near = df[df.index <= target_dt_ist + timedelta(minutes=10)]
            if near.empty:
                return None
            price = float(near.iloc[0]['Close'])
        else:
            price = float(past.iloc[-1]['Close'])

        return round(price, 2)

    except Exception as e:
        print(f"    [Error] Angel One candle fetch for {ticker}: {e}")
        return None

def get_price_yahoo_fallback(ticker, target_dt_ist):
    """Fallback: Yahoo Finance 2-day 1-min chart."""
    try:
        import requests
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2d&interval=1m"
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']

        best_price = None
        best_dt = None
        for ts, cl in zip(timestamps, closes):
            if cl is None:
                continue
            bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
            if bar_dt <= target_dt_ist:
                best_price = cl
                best_dt = bar_dt

        if best_price:
            print(f"    [Yahoo] {ticker} @ {best_dt.strftime('%H:%M')}: {best_price:.2f}")
            return round(best_price, 2)
    except Exception as e:
        print(f"    [Yahoo fallback error] {ticker}: {e}")
    return None

# ── Connect to DB ──
conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ── Get all active signals with their news time ──
c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, si.status,
           n.news_time, n.headline
    FROM stock_impact si
    JOIN news n ON si.news_id = n.id
    WHERE si.status IN ('Active View')
    ORDER BY si.id DESC
""")
rows = c.fetchall()
print(f"Found {len(rows)} active signals to check\n")

market_hours_signals = []
after_hours_signals = []

for r in rows:
    try:
        pub_dt = parsedate_to_datetime(r['news_time']).astimezone(IST)
        if is_market_hours(pub_dt):
            market_hours_signals.append((r, pub_dt))
        else:
            after_hours_signals.append((r, pub_dt))
    except Exception as e:
        print(f"  [Parse error] ID={r['id']} {r['ticker']}: {e}")

print(f"Market-hours signals (need real base_price): {len(market_hours_signals)}")
print(f"After-hours signals (should stay at 0%):     {len(after_hours_signals)}\n")

# ── Ensure Angel One session ──
print("Connecting to Angel One...")
ao._ensure_session()
ao._load_scrip_master()
time.sleep(2)

# ── Restore base_price for market-hours signals ──
fixed = 0
skipped = 0

print("=== Restoring market-hours base prices ===")
for (r, pub_dt) in market_hours_signals:
    sid = r['id']
    ticker = r['ticker']
    bp = r['base_price'] or 0
    cp = r['current_price'] or 0
    stored_pct = r['estimated_change_percent'] or 0

    print(f"\n  ID={sid} {ticker} | news={pub_dt.strftime('%d-%b %H:%M IST')} | cur={cp}")
    print(f"    current base_price={bp} (stored_pct={stored_pct}%)")

    # If base == current, it was wrongly overwritten — restore it
    if abs(bp - cp) < 0.5:  # Less than 0.5 rupee diff = likely overwritten
        # Try Angel One first
        real_base = get_price_at_time_angelone(ticker, pub_dt)

        # Fallback to Yahoo
        if real_base is None or real_base <= 0:
            real_base = get_price_yahoo_fallback(ticker, pub_dt)

        if real_base and real_base > 0 and cp > 0:
            new_pct = round((cp - real_base) / real_base * 100, 2)
            print(f"    RESTORED base={real_base} -> pct={new_pct}%")
            c.execute("""
                UPDATE stock_impact
                SET base_price = ?, estimated_change_percent = ?
                WHERE id = ?
            """, (real_base, new_pct, sid))
            fixed += 1
        else:
            print(f"    SKIPPED — could not fetch price for {ticker} at {pub_dt.strftime('%H:%M')}")
            skipped += 1
    else:
        print(f"    OK — base={bp} != cur={cp}, no overwrite needed")
        skipped += 1

    time.sleep(0.3)  # Rate limit Angel One API

conn.commit()

# ── Verify after-hours signals are 0% ──
print(f"\n=== Verifying after-hours signals (should all be 0%) ===")
wrong_afterhours = 0
for (r, pub_dt) in after_hours_signals:
    bp = r['base_price'] or 0
    cp = r['current_price'] or 0
    if bp > 0 and cp > 0 and abs(bp - cp) > 0.5:
        print(f"  [MISMATCH] ID={r['id']} {r['ticker']} news={pub_dt.strftime('%H:%M')} base={bp} cur={cp}")
        # Fix it
        c.execute("UPDATE stock_impact SET base_price=?, estimated_change_percent=0.0 WHERE id=?",
                  (cp, r['id']))
        wrong_afterhours += 1

if wrong_afterhours:
    conn.commit()
    print(f"  Fixed {wrong_afterhours} after-hours mismatches")
else:
    print("  All after-hours signals are correctly at 0%")

# ── Final summary ──
print(f"\n=== DONE ===")
print(f"  Market-hours signals fixed: {fixed}")
print(f"  Skipped (no data/already ok): {skipped}")

print(f"\n=== Final State (Active Signals) ===")
c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, si.status, n.news_time
    FROM stock_impact si JOIN news n ON si.news_id = n.id
    WHERE si.status = 'Active View'
    ORDER BY si.id DESC LIMIT 20
""")
for r in c.fetchall():
    bp = r['base_price'] or 0
    cp = r['current_price'] or 0
    try:
        pub_ist = parsedate_to_datetime(r['news_time']).astimezone(IST)
        time_str = pub_ist.strftime('%H:%M')
        mkt = "MKTHR" if is_market_hours(pub_ist) else "AFTER"
    except:
        time_str = "?"
        mkt = "?"
    pct = round((cp - bp) / bp * 100, 2) if bp > 0 else 0
    print(f"  ID={r['id']:>3} {r['ticker']:18s} [{mkt} {time_str}] base={bp:>9.2f} cur={cp:>9.2f} pct={pct:>6.2f}%")

conn.close()
