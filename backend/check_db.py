import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import sqlite3

conn = sqlite3.connect('c:/Project rohan/Alpha_Lens/backend/news_cache.db')
c = conn.cursor()

# Count updated vs stale
c.execute("SELECT COUNT(*) FROM stock_impact WHERE ABS(current_price - base_price) < 0.01 AND base_price > 0")
stale = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM stock_impact WHERE ABS(current_price - base_price) >= 0.01")
updated = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM stock_impact")
total = c.fetchone()[0]
print(f"Total signals: {total}")
print(f"Updated (price != base): {updated}")
print(f"Stale (price == base): {stale}")

# Status breakdown
print("\nStatus breakdown:")
c.execute("SELECT status, COUNT(*) FROM stock_impact GROUP BY status ORDER BY COUNT(*) DESC")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")

# PNB specifically
print("\nPNB signals:")
c.execute("SELECT id, base_price, current_price, estimated_change_percent, status FROM stock_impact WHERE ticker='PNB.NS' ORDER BY id DESC LIMIT 5")
for row in c.fetchall():
    print(f"  ID={row[0]} base={row[1]} curr={row[2]} pct={row[3]} status={row[4]}")

conn.close()
