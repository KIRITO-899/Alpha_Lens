"""
Comprehensive check and fix of current_price for all active signals.
Uses Angel One's actual daily candle close (not LTP which can be stale/wrong).
For signals created on May 5 or May 4, fetches the official closing price
from Angel One's OHLC candle API and compares with what's stored.
"""
import sqlite3, sys, io, os, time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import angelone_shim as ao

IST = timezone(timedelta(hours=5, minutes=30))

def get_official_close(ticker, trade_date_ist):
    """
    Get the official closing price for a ticker on a specific trading date
    using Angel One's daily OHLC candle (most authoritative source).
    """
    try:
        exchange, token = ao._get_exchange_token(ticker)
        if not exchange or not token:
            return None

        # Fetch daily candles for a window including the target date
        from_dt = trade_date_ist.replace(hour=9, minute=0, second=0)
        to_dt   = trade_date_ist.replace(hour=23, minute=59, second=0)

        df = ao._ao_get_candle(exchange, token, 'ONE_DAY', from_dt, to_dt)
        if df.empty:
            return None

        df.index = df.index.tz_convert(IST)
        target_date = trade_date_ist.date()

        for idx, row in df.iterrows():
            if idx.date() == target_date:
                return round(float(row['Close']), 2)
    except Exception as e:
        print(f"    [AngelOne daily error] {ticker}: {e}")

    # Fallback: 1-min candle at exactly 3:29 PM
    try:
        exchange, token = ao._get_exchange_token(ticker)
        if not exchange or not token:
            return None

        close_time = trade_date_ist.replace(hour=15, minute=28, second=0)
        to_time    = trade_date_ist.replace(hour=15, minute=31, second=0)

        df = ao._ao_get_candle(exchange, token, 'ONE_MINUTE', close_time, to_time)
        if not df.empty:
            df.index = df.index.tz_convert(IST)
            # Get the 3:29/3:30 candle close
            relevant = df[df.index.date == trade_date_ist.date()]
            if not relevant.empty:
                return round(float(relevant.iloc[-1]['Close']), 2)
    except Exception as e:
        print(f"    [AngelOne 1m close error] {ticker}: {e}")

    return None

# Connect to DB
conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get all active signals
rows = c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, si.status, n.news_time
    FROM stock_impact si
    JOIN news n ON si.news_id = n.id
    WHERE si.status = 'Active View'
    ORDER BY si.id DESC
""").fetchall()

print(f"Checking {len(rows)} active signals...\n")

# Ensure Angel One session
ao._ensure_session()
ao._load_scrip_master()
time.sleep(1)

# Cache: (ticker, date) -> close_price
close_cache = {}
fixes = 0

for r in rows:
    try:
        pub_dt = parsedate_to_datetime(r['news_time']).astimezone(IST)
    except:
        continue

    # Only market-hours signals
    t = pub_dt.hour * 60 + pub_dt.minute
    is_market = (pub_dt.weekday() < 5 and (9*60+15) <= t <= (15*60+30))
    if not is_market:
        continue

    ticker = r['ticker']
    base   = r['base_price'] or 0
    stored = r['current_price'] or 0
    trade_date = pub_dt.replace(hour=12, minute=0, second=0, microsecond=0)  # noon on trading day

    cache_key = (ticker, trade_date.date())
    if cache_key not in close_cache:
        print(f"  Fetching {ticker} close for {trade_date.date()}...", end='', flush=True)
        close_p = get_official_close(ticker, trade_date)
        close_cache[cache_key] = close_p
        print(f" ₹{close_p}" if close_p else " FAILED")
        time.sleep(0.2)

    close_p = close_cache.get(cache_key)
    if not close_p or close_p <= 0 or base <= 0:
        continue

    new_pct   = round((close_p - base) / base * 100, 2)
    old_pct   = r['estimated_change_percent'] or 0
    price_diff = abs(close_p - stored)

    status = ""
    if price_diff > 0.1:
        status = f"UPDATED (was {stored:.2f} -> {close_p:.2f})"
        c.execute("""
            UPDATE stock_impact
            SET current_price = ?, estimated_change_percent = ?
            WHERE id = ?
        """, (close_p, new_pct, r['id']))
        fixes += 1
    else:
        status = "OK"

    print(f"  ID={r['id']:>3} {ticker:18s} | base={base:>9.2f} stored={stored:>9.2f} official_close={close_p:>9.2f} pct={new_pct:>+7.2f}% [{status}]")

conn.commit()
print(f"\n{'='*60}")
print(f"Total fixed: {fixes}")

# Show final state
print(f"\n=== Final active signal prices ===")
rows2 = c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, n.news_time
    FROM stock_impact si
    JOIN news n ON si.news_id = n.id
    WHERE si.status = 'Active View'
    ORDER BY si.id DESC LIMIT 25
""").fetchall()

for r in rows2:
    bp = r['base_price'] or 0
    cp = r['current_price'] or 0
    pct = r['estimated_change_percent'] or 0
    try:
        pub_ist = parsedate_to_datetime(r['news_time']).astimezone(IST)
        time_s = pub_ist.strftime('%d-%b %H:%M')
    except:
        time_s = "?"
    print(f"  ID={r['id']:>3} {r['ticker']:18s} [{time_s}] base={bp:>9.2f} cur={cp:>9.2f} pct={pct:>+7.2f}%")

conn.close()
print("\nDone!")
