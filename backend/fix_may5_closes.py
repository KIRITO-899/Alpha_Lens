"""
Fix current_price for all May 5 market-hours signals using 
Yahoo 1-min data at 3:30 PM close (since daily endpoint has no data for today).
"""
import sqlite3, sys, io, requests
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

IST = timezone(timedelta(hours=5, minutes=30))
CLOSE_TIME = datetime(2026, 5, 5, 15, 30, 0, tzinfo=IST)

def get_close_price_1m(ticker):
    """Get the 3:30 PM close price from Yahoo 1-min data for May 5."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2d&interval=1m"
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']

        # Find the candle at or closest to 3:30 PM on May 5
        may5_close_window_start = datetime(2026, 5, 5, 15, 28, 0, tzinfo=IST)
        may5_close_window_end   = datetime(2026, 5, 5, 15, 31, 0, tzinfo=IST)

        best_price = None
        for ts, cl in zip(timestamps, closes):
            if cl is None:
                continue
            bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
            if may5_close_window_start <= bar_dt <= may5_close_window_end:
                best_price = cl  # last one wins = closest to 3:30 PM

        if best_price:
            return round(float(best_price), 2)

        # Fallback: last bar before 3:31 PM on May 5
        last_before_close = None
        cutoff = datetime(2026, 5, 5, 15, 31, 0, tzinfo=IST)
        start  = datetime(2026, 5, 5,  9, 15, 0, tzinfo=IST)
        for ts, cl in zip(timestamps, closes):
            if cl is None:
                continue
            bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
            if start <= bar_dt <= cutoff:
                last_before_close = cl
        if last_before_close:
            return round(float(last_before_close), 2)
    except Exception as e:
        print(f"    [Error] {ticker}: {e}")
    return None

conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get all active signals from May 5 during market hours
rows = c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, n.news_time
    FROM stock_impact si
    JOIN news n ON si.news_id = n.id
    WHERE si.status = 'Active View'
    ORDER BY si.id DESC
""").fetchall()

# Filter: only May 5 market-hours signals that still have stale current_price
may5_signals = []
for r in rows:
    try:
        pub_dt = parsedate_to_datetime(r['news_time']).astimezone(IST)
    except:
        continue
    t = pub_dt.hour * 60 + pub_dt.minute
    is_market = (pub_dt.weekday() < 5 and (9*60+15) <= t <= (15*60+30))
    if is_market and pub_dt.date() == datetime(2026, 5, 5, tzinfo=IST).date():
        may5_signals.append((r, pub_dt))

print(f"Found {len(may5_signals)} May 5 market-hours active signals\n")

# Fetch close prices (deduplicated by ticker)
ticker_closes = {}
seen = set()
for (r, pub_dt) in may5_signals:
    ticker = r['ticker']
    if ticker not in seen:
        seen.add(ticker)
        close_p = get_close_price_1m(ticker)
        ticker_closes[ticker] = close_p
        print(f"  {ticker:18s}: 3:30 PM close = {'₹'+str(close_p) if close_p else 'FAILED'}")

print()
fixes = 0
for (r, pub_dt) in may5_signals:
    ticker   = r['ticker']
    base     = r['base_price'] or 0
    close_p  = ticker_closes.get(ticker)

    if not close_p or close_p <= 0 or base <= 0:
        print(f"  [SKIP] ID={r['id']} {ticker} — no close price")
        continue

    new_pct = round((close_p - base) / base * 100, 2)
    old_cur = r['current_price'] or 0
    old_pct = r['estimated_change_percent'] or 0

    print(f"  ID={r['id']:>3} {ticker:18s} | base={base:>9.2f} old={old_cur:>9.2f} close={close_p:>9.2f} pct={new_pct:>+7.2f}%")
    c.execute("""
        UPDATE stock_impact
        SET current_price = ?, estimated_change_percent = ?
        WHERE id = ?
    """, (close_p, new_pct, r['id']))
    fixes += 1

conn.commit()
print(f"\n{fixes} signals updated to use actual 3:30 PM close price.")
conn.close()
