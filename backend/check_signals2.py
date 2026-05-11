import sqlite3
c = sqlite3.connect('news_cache.db')
print("=== News IDs with signals (last 7 days, backend DB) ===")
rows = c.execute("""
    SELECT n.id, substr(n.headline,1,60), count(si.id) as cnt
    FROM news n
    LEFT JOIN stock_impact si ON n.id=si.news_id
    GROUP BY n.id
    HAVING count(si.id) > 0
    ORDER BY n.created_at DESC
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"id={r[0]:5d} | sigs={r[2]} | {r[1]}")
    
print(f"\nTotal news: {c.execute('SELECT count(*) FROM news').fetchone()[0]}")
print(f"Total signals: {c.execute('SELECT count(*) FROM stock_impact').fetchone()[0]}")
print(f"\n=== Latest news (what API serves first) ===")
rows2 = c.execute("SELECT id, substr(headline,1,60), created_at FROM news ORDER BY created_at DESC LIMIT 5").fetchall()
for r in rows2:
    print(f"id={r[0]:5d} | {r[2]} | {r[1]}")
