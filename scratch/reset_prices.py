"""One-time script: reset current_price = base_price for all Active View stocks.
This ensures 0% change is shown while market is closed."""
import sqlite3

conn = sqlite3.connect('news_cache.db')
c = conn.cursor()
c.execute("UPDATE stock_impact SET current_price = base_price WHERE status = 'Active View'")
print(f"Reset {c.rowcount} active stock prices to base_price (0% change)")
conn.commit()
conn.close()
