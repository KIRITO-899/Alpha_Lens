import sqlite3

conn = sqlite3.connect('backend/news_cache.db')
c = conn.cursor()
c.execute("""
    SELECT si.id, n.headline, si.ticker, si.impact, si.base_price, si.current_price, 
           si.status, si.estimated_change_percent, si.created_at
    FROM stock_impact si 
    JOIN news n ON si.news_id=n.id 
    WHERE si.ticker='TATATECH.NS' 
    ORDER BY si.created_at DESC 
    LIMIT 5
""")
rows = c.fetchall()
print("=== TATATECH.NS signals ===")
for r in rows:
    print(f"  ID={r[0]}, base={r[4]}, current={r[5]}, status={r[6]}, est_change={r[7]}, created={r[8]}")
    print(f"  Headline: {r[1][:80]}")
    print()

# Check total signal count
c.execute("SELECT COUNT(*) FROM stock_impact")
total = c.fetchone()[0]
print(f"Total stock_impact rows: {total}")

c.execute("SELECT COUNT(*) FROM news")
total_news = c.fetchone()[0]
print(f"Total news rows: {total_news}")

# Check status distribution
c.execute("SELECT status, COUNT(*) FROM stock_impact GROUP BY status")
statuses = c.fetchall()
print("\nStatus distribution:")
for s in statuses:
    print(f"  {s[0]}: {s[1]}")

# Check if there are stop loss hits that shouldn't be
c.execute("""
    SELECT si.ticker, si.impact, si.base_price, si.current_price, 
           si.estimated_change_percent, si.status, si.created_at
    FROM stock_impact si
    WHERE si.status = 'Stop Loss Hit'
    ORDER BY si.created_at DESC
    LIMIT 10
""")
stops = c.fetchall()
print("\nRecent Stop Loss Hits:")
for s in stops:
    direction = "BULL" if "bullish" in s[1].lower() else "BEAR"
    calc = ((s[3]-s[2])/s[2]*100) if s[2]>0 else 0
    print(f"  {s[0]} [{direction}] base={s[2]}, curr={s[3]}, calc_diff={calc:.2f}%, stored_diff={s[4]}, {s[6]}")

conn.close()
