"""
For all active signals created DURING market hours yesterday (May 5),
update current_price to the ACTUAL market close price using Yahoo Finance daily OHLC.
This ensures the percentage shown = real change from news time to close.
Also updates estimated_change_percent accordingly.
"""
import sqlite3, sys, io, requests, os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

IST = timezone(timedelta(hours=5, minutes=30))

def get_closing_price_yahoo(ticker, date_ist):
    """Get the official closing price for a ticker on a given date via Yahoo daily OHLC."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']

        target_date = date_ist.date()
        for ts, cl in zip(timestamps, closes):
            if cl is None:
                continue
            bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
            if bar_dt.date() == target_date:
                return round(float(cl), 2)
    except Exception as e:
        print(f"    [Yahoo daily error] {ticker}: {e}")
    return None

conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get all active signals with their news_time
rows = c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, si.status, n.news_time
    FROM stock_impact si
    JOIN news n ON si.news_id = n.id
    WHERE si.status = 'Active View'
    ORDER BY si.id DESC
""").fetchall()

print(f"Checking {len(rows)} active signals for stale current_price...\n")

fixes = 0
for r in rows:
    try:
        pub_dt = parsedate_to_datetime(r['news_time']).astimezone(IST)
    except:
        continue

    # Only process market-hours signals from yesterday (or earlier today)
    t = pub_dt.hour * 60 + pub_dt.minute
    is_market = (pub_dt.weekday() < 5 and (9*60+15) <= t <= (15*60+30))
    if not is_market:
        continue

    ticker = r['ticker']
    base   = r['base_price'] or 0
    cur    = r['current_price'] or 0

    # Fetch the closing price on the day of the news
    close_price = get_closing_price_yahoo(ticker, pub_dt)
    if close_price is None or close_price <= 0:
        print(f"  [SKIP] ID={r['id']} {ticker} — could not fetch close for {pub_dt.date()}")
        continue

    new_pct = round((close_price - base) / base * 100, 2) if base > 0 else 0

    # Only update if it's meaningfully different from what's stored
    if abs(close_price - cur) > 0.1 or abs(new_pct - (r['estimated_change_percent'] or 0)) > 0.05:
        print(f"  ID={r['id']:>3} {ticker:18s} | base={base:>9.2f} old_cur={cur:>9.2f} new_cur={close_price:>9.2f} pct={new_pct:>+7.2f}%")
        c.execute("""
            UPDATE stock_impact
            SET current_price = ?, estimated_change_percent = ?
            WHERE id = ?
        """, (close_price, new_pct, r['id']))
        fixes += 1
    else:
        print(f"  ID={r['id']:>3} {ticker:18s} | base={base:>9.2f} cur={cur:>9.2f} pct={new_pct:>+7.2f}% [OK]")

conn.commit()
print(f"\n{fixes} signals updated with actual closing prices.")
conn.close()
