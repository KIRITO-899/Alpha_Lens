import sqlite3
conn=sqlite3.connect('news_cache.db')
c=conn.cursor()
c.execute("SELECT id, created_at FROM news WHERE headline LIKE '%Hero MotoCorp Q4%'")
print(c.fetchall())
conn.close()
