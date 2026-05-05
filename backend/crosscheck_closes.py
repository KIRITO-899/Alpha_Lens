"""
Cross-check current_price in DB against Yahoo Finance official closes.
Yahoo Finance's 1-min data for 'range=5d' goes back further than 2d.
"""
import sqlite3, sys, io, requests
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
IST = timezone(timedelta(hours=5, minutes=30))

def get_nse_close_yahoo(ticker, trade_date):
    """Get NSE official close from Yahoo Finance 5d/1m data."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1m"
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']

        # Find last bar on the target date between 15:28-15:31 IST
        win_start = datetime(trade_date.year, trade_date.month, trade_date.day, 15, 28, tzinfo=IST)
        win_end   = datetime(trade_date.year, trade_date.month, trade_date.day, 15, 31, tzinfo=IST)

        best = None
        for ts, cl in zip(timestamps, closes):
            if cl is None:
                continue
            bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
            if win_start <= bar_dt <= win_end:
                best = round(float(cl), 2)
        return best
    except Exception as e:
        return None

conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

rows = c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, n.news_time
    FROM stock_impact si
    JOIN news n ON si.news_id = n.id
    WHERE si.status = 'Active View'
    ORDER BY si.id DESC
""").fetchall()

# Gather unique (ticker, date) combos for market-hours signals
ticker_date_set = {}
for r in rows:
    try:
        pub_dt = parsedate_to_datetime(r['news_time']).astimezone(IST)
    except:
        continue
    t = pub_dt.hour * 60 + pub_dt.minute
    if pub_dt.weekday() < 5 and (9*60+15) <= t <= (15*60+30):
        key = (r['ticker'], pub_dt.date())
        if key not in ticker_date_set:
            ticker_date_set[key] = pub_dt.date()

print(f"Fetching official closes for {len(ticker_date_set)} (ticker,date) combos...\n")

# Fetch closes
official_closes = {}
for (ticker, trade_date), _ in ticker_date_set.items():
    close_p = get_nse_close_yahoo(ticker, datetime(trade_date.year, trade_date.month, trade_date.day, 12, tzinfo=IST))
    official_closes[(ticker, trade_date)] = close_p
    status = f"₹{close_p:.2f}" if close_p else "FAILED"
    print(f"  {ticker:18s} {trade_date}: close={status}")

print("\n=== Comparison: stored vs official close ===")
print(f"{'ID':>4} {'Ticker':18s} {'Date':10s} {'Base':>9} {'Stored':>9} {'Official':>9} {'Stored%':>8} {'Official%':>9} Status")
print("-"*85)

fixes = 0
for r in rows:
    try:
        pub_dt = parsedate_to_datetime(r['news_time']).astimezone(IST)
    except:
        continue
    t = pub_dt.hour * 60 + pub_dt.minute
    if not (pub_dt.weekday() < 5 and (9*60+15) <= t <= (15*60+30)):
        continue

    ticker   = r['ticker']
    base     = r['base_price'] or 0
    stored   = r['current_price'] or 0
    trade_date = pub_dt.date()
    official = official_closes.get((ticker, trade_date))

    stored_pct   = round((stored   - base) / base * 100, 2) if base > 0 else 0
    official_pct = round((official - base) / base * 100, 2) if (official and base > 0) else None

    discrepancy = ""
    if official and abs(official - stored) > 0.5:
        discrepancy = "*** WRONG ***"
        # Fix it
        c.execute("UPDATE stock_impact SET current_price=?, estimated_change_percent=? WHERE id=?",
                  (official, official_pct, r['id']))
        fixes += 1

    off_str = f"₹{official:.2f}" if official else "N/A"
    off_pct = f"{official_pct:+.2f}%" if official_pct is not None else "N/A"
    print(f"{r['id']:>4} {ticker:18s} {str(trade_date):10s} {base:>9.2f} {stored:>9.2f} {off_str:>9} {stored_pct:>+7.2f}% {off_pct:>9} {discrepancy}")

conn.commit()
print(f"\nFixed {fixes} signals with wrong current_price.")
conn.close()
