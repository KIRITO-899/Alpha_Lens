"""
Diagnostic script to understand the current signal status issue
"""
import sqlite3
from datetime import datetime, timedelta

DB_PATH = r'c:\Project rohan\Alpha_Lens\news_cache.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

###################
# Query 1: Status breakdown
###################
print("=== SIGNAL STATUS BREAKDOWN ===")
c.execute("SELECT status, COUNT(*) as cnt FROM stock_impact GROUP BY status")
for row in c.fetchall():
    print(f"{row['status']:<30} : {row['cnt']}")

###################
# Query 2: Recent active signals with details
###################
print("\n=== RECENT ACTIVE SIGNALS (Last 5) ===")
c.execute("""
    SELECT id, ticker, impact, base_price, current_price, 
           ROUND((current_price - base_price) / base_price * 100, 2) as diff_pct,
           status, created_at
    FROM stock_impact
    WHERE status = 'Active View'
    ORDER BY created_at DESC
    LIMIT 5
""")
for row in c.fetchall():
    print(f"[{row['id']}] {row['ticker']:<12} {row['impact']:<12} | "
          f"Base: {row['base_price']:<9} Current: {row['current_price']:<9} | "
          f"Diff: {row['diff_pct']:>7}% | Status: {row['status']}")

###################
# Query 3: Stopped/Target signals  
###################
print("\n=== STOPPED/TARGET HIT SIGNALS ===")
c.execute("""
    SELECT id, ticker, impact, base_price, current_price,
           ROUND((current_price - base_price) / base_price * 100, 2) as diff_pct,
           status, estimated_change_percent, created_at
    FROM stock_impact
    WHERE status IN ('Stop Loss Hit', 'Predicted Target Hit')
    ORDER BY created_at DESC
    LIMIT 10
""")
results = c.fetchall()
if results:
    for row in results:
        print(f"[{row['id']}] {row['ticker']:<12} {row['impact']:<12} | "
              f"Base: {row['base_price']:<9} Current: {row['current_price']:<9} | "
              f"Calc Diff: {row['diff_pct']:>7}% | DB Diff: {row['estimated_change_percent']:>7}% | "
              f"Status: {row['status']}")
else:
    print("(No stopped/target signals found)")

###################
# Query 4: RELIANCE.NS specifically
###################
print("\n=== RELIANCE.NS ALL RECORDS ===")
c.execute("""
    SELECT id, ticker, impact, base_price, current_price,
           ROUND((current_price - base_price) / base_price * 100, 2) as diff_pct,
           status, estimated_change_percent, created_at
    FROM stock_impact
    WHERE ticker = 'RELIANCE.NS'
    ORDER BY created_at DESC
""")
results = c.fetchall()
if results:
    for row in results:
        print(f"[{row['id']}] {row['impact']:<12} | "
              f"Base: {row['base_price']:<9} Current: {row['current_price']:<9} | "
              f"Calc Diff: {row['diff_pct']:>7}% | DB Diff: {row['estimated_change_percent']:>7}% | "
              f"Status: {row['status']:<25} Created: {row['created_at']}")
else:
    print("(No RELIANCE.NS records found)")

conn.close()
