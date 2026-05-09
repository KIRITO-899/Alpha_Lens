import sqlite3
conn=sqlite3.connect('news_cache.db')
c=conn.cursor()
c.execute("SELECT id, created_at FROM news WHERE id IN (121, 130, 132)")
for row in c.fetchall():
  print(row)
conn.close()
