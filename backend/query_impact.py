import sqlite3
conn=sqlite3.connect('news_cache.db')
c=conn.cursor()
c.execute("SELECT id, ticker, base_price, current_price, status FROM stock_impact WHERE news_id IN (121, 130, 132)")
print(c.fetchall())
conn.close()
