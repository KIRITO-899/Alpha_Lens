"""
Check what BSE.NS actually did from 1:44 PM to 3:30 PM close on May 5.
Also check current price from Angel One right now.
"""
import sys, io, os, requests
from datetime import datetime, timedelta, timezone
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import angelone_shim as ao

IST = timezone(timedelta(hours=5, minutes=30))

print("=== BSE.NS full afternoon on May 5 (from Yahoo 1-min) ===")
try:
    headers = {"User-Agent": "Mozilla/5.0"}
    # Fetch 5-day 1-min data to get all of May 5
    url = "https://query1.finance.yahoo.com/v8/finance/chart/BSE.NS?range=5d&interval=1m"
    resp = requests.get(url, headers=headers, timeout=10)
    data = resp.json()
    result = data['chart']['result'][0]
    timestamps = result['timestamp']
    closes = result['indicators']['quote'][0]['close']
    highs  = result['indicators']['quote'][0].get('high', [None]*len(timestamps))
    lows   = result['indicators']['quote'][0].get('low',  [None]*len(timestamps))

    # Show candles from 1:44 PM to 3:30 PM on May 5
    start = datetime(2026, 5, 5, 13, 44, 0, tzinfo=IST)
    end   = datetime(2026, 5, 5, 15, 35, 0, tzinfo=IST)

    print(f"\nBSE.NS candles from 1:44 PM to 3:30 PM IST on 5-May-2026:")
    found = []
    for ts, cl, hi, lo in zip(timestamps, closes, highs, lows):
        bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
        if start <= bar_dt <= end and cl is not None:
            found.append((bar_dt, cl, hi, lo))

    if found:
        base = found[0][1]  # price at 1:44 PM
        print(f"{'Time':>12}  {'Close':>8}  {'High':>8}  {'Low':>8}  {'Chg%':>7}")
        print("-" * 50)
        for dt, cl, hi, lo in found:
            chg = round((cl - base) / base * 100, 2) if base > 0 else 0
            print(f"{dt.strftime('%H:%M IST'):>12}  {cl:>8.2f}  {hi:>8.2f}  {lo:>8.2f}  {chg:>+7.2f}%")
        
        close_price = found[-1][1]
        max_high = max(h for _, _, h, _ in found if h)
        min_low  = min(l for _, _, _, l in found if l)
        print(f"\n  Base at 1:44 PM  : ₹{base:.2f}")
        print(f"  Close at 3:30 PM : ₹{close_price:.2f}  ({round((close_price-base)/base*100,2):+.2f}%)")
        print(f"  Intraday HIGH    : ₹{max_high:.2f}  ({round((max_high-base)/base*100,2):+.2f}%)")
        print(f"  Intraday LOW     : ₹{min_low:.2f}  ({round((min_low-base)/base*100,2):+.2f}%)")
    else:
        print("  No candles found for that window")
        print("  (Yahoo Finance may not have data older than 1-2 days for 1-min intervals)")

except Exception as e:
    print(f"  Yahoo error: {e}")

# Also check Angel One current quote for BSE.NS
print("\n=== BSE.NS current quote from Angel One ===")
try:
    ao._ensure_session()
    ltp, prev, high, low = ao._get_cached_quote('BSE.NS')
    print(f"  LTP      : ₹{ltp:.2f}")
    print(f"  PrevClose: ₹{prev:.2f}")
    print(f"  DayHigh  : ₹{high:.2f}")
    print(f"  DayLow   : ₹{low:.2f}")
    print(f"  Day chg  : {round((ltp-prev)/prev*100,2):+.2f}% (today vs yesterday)")
except Exception as e:
    print(f"  Angel One error: {e}")
