import sqlite3
from datetime import datetime, timedelta, timezone

conn = sqlite3.connect('backend/news_cache.db')
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM news")
total = c.fetchone()[0]
print(f"Total news in DB: {total}")

c.execute("SELECT MIN(created_at), MAX(created_at) FROM news")
row = c.fetchone()
print(f"Date range: {row[0]}  -->  {row[1]}")

seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
c.execute("SELECT COUNT(*) FROM news WHERE created_at >= ?", (seven_days_ago,))
recent = c.fetchone()[0]
print(f"News in last 7 days (shown to user): {recent}")
print(f"7-day cutoff is: {seven_days_ago}")

print("\n--- Latest 5 headlines ---")
c.execute("SELECT id, headline, created_at FROM news ORDER BY created_at DESC LIMIT 5")
for row in c.fetchall():
    print(f"  [{row[2]}] {row[1][:80]}")

conn.close()
