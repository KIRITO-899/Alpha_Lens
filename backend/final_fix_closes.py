"""
FINAL FIX: Update current_price for ALL active signals using Yahoo's
official 3:30 PM close (5d/1m window 15:28-15:31 IST).
This fixes signals where Angel One's LTP != official NSE close.
"""
import sqlite3, sys, io, requests
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
IST = timezone(timedelta(hours=5, minutes=30))


def yahoo_official_close(ticker):
    """Get the most recent official 3:30 PM close from Yahoo 5d/1m."""
    try:
        h = {"User-Agent": "Mozilla/5.0"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1m"
        r = requests.get(url, headers=h, timeout=10)
        data = r.json()
        result = data['chart']['result'][0]
        tss    = result['timestamp']
        closes = result['indicators']['quote'][0]['close']
        best_p = None
        best_dt = None
        for ts, cl in zip(tss, closes):
            if cl is None:
                continue
            bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
            bar_t  = bar_dt.hour * 60 + bar_dt.minute
            if (15 * 60 + 28) <= bar_t <= (15 * 60 + 31):
                best_p  = round(float(cl), 2)
                best_dt = bar_dt
        return best_p, best_dt
    except Exception as e:
        return None, None


conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# All active signals
rows = c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, si.status, n.news_time
    FROM stock_impact si
    JOIN news n ON si.news_id = n.id
    WHERE si.status = 'Active View'
    ORDER BY si.id DESC
""").fetchall()

print(f"Processing {len(rows)} active signals...\n")

# Cache official closes per ticker
cache = {}
fixes = 0

for r in rows:
    ticker = r['ticker']
    base   = r['base_price'] or 0
    stored = r['current_price'] or 0

    if ticker not in cache:
        close_p, close_dt = yahoo_official_close(ticker)
        cache[ticker] = (close_p, close_dt)
        dt_str = close_dt.strftime('%d-%b %H:%M IST') if close_dt else "N/A"
        status = f"₹{close_p:.2f} @ {dt_str}" if close_p else "FAILED"
        print(f"  {ticker:18s}: {status}")

    close_p, close_dt = cache[ticker]
    if not close_p or close_p <= 0:
        print(f"  [SKIP] ID={r['id']} {ticker} — no close available")
        continue

    if base <= 0:
        continue

    new_pct = round((close_p - base) / base * 100, 2)

    if abs(close_p - stored) > 0.1:
        print(f"  FIX ID={r['id']:>3} {ticker:18s} | base={base:>9.2f} stored={stored:>9.2f} → close={close_p:>9.2f} ({new_pct:>+.2f}%)")
        c.execute("UPDATE stock_impact SET current_price=?, estimated_change_percent=? WHERE id=?",
                  (close_p, new_pct, r['id']))
        fixes += 1

conn.commit()
print(f"\n{fixes} signals updated.")

# Show final state
print("\n=== Final Active Signals ===")
rows2 = c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, n.news_time
    FROM stock_impact si JOIN news n ON si.news_id = n.id
    WHERE si.status = 'Active View'
    ORDER BY si.id DESC LIMIT 30
""").fetchall()

for r in rows2:
    bp = r['base_price'] or 0
    cp = r['current_price'] or 0
    pct = r['estimated_change_percent'] or 0
    try:
        pub = parsedate_to_datetime(r['news_time']).astimezone(IST)
        ts  = pub.strftime('%d-%b %H:%M')
    except:
        ts = "?"
    flag = " ← STILL 0" if abs(cp - bp) < 0.1 and abs(pct) < 0.01 else ""
    print(f"  ID={r['id']:>3} {r['ticker']:18s} [{ts}] base={bp:>9.2f} cur={cp:>9.2f} pct={pct:>+7.2f}%{flag}")

conn.close()
