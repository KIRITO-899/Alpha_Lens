import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'c:/Project rohan/Alpha_Lens/backend')
from dotenv import load_dotenv
load_dotenv('c:/Project rohan/Alpha_Lens/.env')
import angelone_shim as yf
import sqlite3, time

time.sleep(2)

# 1. Check real Angel One price for PNB
print("=== Angel One LTP for PNB.NS ===")
ltp, prev = yf.get_ltp("PNB.NS")
print(f"LTP: {ltp}, Prev Close: {prev}")
fi = yf.Ticker("PNB.NS").fast_info
print(f"fast_info: last={fi.last_price}, prev={fi.previous_close}, high={fi.day_high}, low={fi.day_low}")

# 2. Check database
print("\n=== Database PNB signals ===")
conn = sqlite3.connect('c:/Project rohan/Alpha_Lens/backend/news_cache.db')
c = conn.cursor()
c.execute("""
    SELECT id, ticker, base_price, current_price, estimated_change_percent, status, impact, created_at
    FROM stock_impact WHERE ticker='PNB.NS'
    ORDER BY created_at DESC LIMIT 5
""")
for row in c.fetchall():
    print(f"  ID={row[0]} base={row[2]} curr={row[3]} pct={row[4]} status={row[5]} impact={row[6]} created={row[7]}")

# 3. Check ALL recent signals (last 20) for the 0% issue
print("\n=== Last 20 signals with 0% or same base/current ===")
c.execute("""
    SELECT id, ticker, base_price, current_price, estimated_change_percent, status, created_at
    FROM stock_impact 
    WHERE ABS(current_price - base_price) < 0.01
    ORDER BY created_at DESC LIMIT 20
""")
for row in c.fetchall():
    print(f"  ID={row[0]} {row[1]:20s} base={row[2]:10.2f} curr={row[3]:10.2f} pct={row[4]} created={row[6]}")

conn.close()
