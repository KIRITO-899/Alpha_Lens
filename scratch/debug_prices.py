"""Debug: check what the API returns for stock changes"""
import sqlite3
import json

conn = sqlite3.connect('news_cache.db')
c = conn.cursor()

# Check stock_impact rows where current_price != base_price
c.execute("""
    SELECT id, ticker, base_price, current_price, status,
           ROUND(((current_price - base_price) / base_price) * 100, 2) as change_pct
    FROM stock_impact
    WHERE ABS(current_price - base_price) > 0.01
    ORDER BY created_at DESC
    LIMIT 20
""")
rows = c.fetchall()

print(f"\n=== Stocks where current_price != base_price ({len(rows)} found) ===")
for r in rows:
    print(f"  ID={r[0]}  {r[1]:20s}  base={r[2]:10.2f}  curr={r[3]:10.2f}  change={r[5]:+.2f}%  status={r[4]}")

# Also count totals
c.execute("SELECT COUNT(*) FROM stock_impact WHERE ABS(current_price - base_price) > 0.01")
total_diff = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM stock_impact")
total = c.fetchone()[0]
print(f"\nTotal rows with change: {total_diff} / {total}")

# Check if base_price == current_price for Active View
c.execute("SELECT COUNT(*) FROM stock_impact WHERE status='Active View' AND ABS(current_price - base_price) > 0.01")
active_diff = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM stock_impact WHERE status='Active View'")
active_total = c.fetchone()[0]
print(f"Active View with change: {active_diff} / {active_total}")

conn.close()
