import sqlite3
conn=sqlite3.connect('news_cache.db')
c=conn.cursor()
c.execute("SELECT id, news_id, created_at FROM stock_impact WHERE id IN (168, 178, 181)")
for row in c.fetchall():
  print(row)
conn.close()
