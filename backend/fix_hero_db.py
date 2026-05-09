import sqlite3
conn=sqlite3.connect('news_cache.db')
c=conn.cursor()
c.execute("UPDATE stock_impact SET created_at='2026-05-05 14:00:00', status='Active View' WHERE news_id IN (121, 130, 132)")
c.execute("UPDATE news SET created_at='2026-05-05 14:00:00' WHERE id IN (121, 130, 132)")
conn.commit()
conn.close()
