import sqlite3, sys, io, requests
from datetime import datetime, timedelta, timezone
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

IST = timezone(timedelta(hours=5, minutes=30))

conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row

# Check the Vedanta/BSE signal specifically
rows = conn.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price, 
           si.estimated_change_percent, si.status, n.news_time, n.headline
    FROM stock_impact si 
    JOIN news n ON si.news_id = n.id
    WHERE n.headline LIKE '%Vedanta%' OR (si.ticker='BSE.NS' AND si.status='Active View')
    ORDER BY si.id DESC LIMIT 10
""").fetchall()

print("=== BSE.NS Active Signals ===")
for r in rows:
    print(f"\nID={r['id']} {r['ticker']}")
    print(f"  headline   : {r['headline'][:70]}")
    print(f"  news_time  : {r['news_time']}")
    print(f"  base_price : {r['base_price']}")
    print(f"  curr_price : {r['current_price']}")
    print(f"  pct        : {r['estimated_change_percent']}%")
    print(f"  status     : {r['status']}")

conn.close()

# Now let's check what BSE.NS 1-min candle actually returned at 1:44 PM on May 5
print("\n=== Fetching BSE.NS 1-min candle at 13:44 IST on May 5 (Yahoo) ===")
try:
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://query1.finance.yahoo.com/v8/finance/chart/BSE.NS?range=2d&interval=1m"
    resp = requests.get(url, headers=headers, timeout=10)
    data = resp.json()
    result = data['chart']['result'][0]
    timestamps = result['timestamp']
    closes = result['indicators']['quote'][0]['close']

    target = datetime(2026, 5, 5, 13, 44, 0, tzinfo=IST)
    
    # Show candles around 1:44 PM on May 5
    print("Candles from 1:40 PM to 1:50 PM IST on May 5:")
    start = datetime(2026, 5, 5, 13, 40, 0, tzinfo=IST)
    end   = datetime(2026, 5, 5, 13, 50, 0, tzinfo=IST)
    
    found = []
    for ts, cl in zip(timestamps, closes):
        if cl is None:
            continue
        bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
        if start <= bar_dt <= end:
            found.append((bar_dt, cl))
    
    if found:
        for dt, cl in found:
            print(f"  {dt.strftime('%H:%M:%S IST')} : {cl:.2f}")
    else:
        print("  No candles found in that range (data may only cover today)")
        # Show last 10 candles available
        print("\nLast 10 available candles:")
        valid = [(ts, cl) for ts, cl in zip(timestamps, closes) if cl is not None]
        for ts, cl in valid[-10:]:
            bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
            print(f"  {bar_dt.strftime('%d-%b %H:%M IST')} : {cl:.2f}")
except Exception as e:
    print(f"  Error: {e}")
