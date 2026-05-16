import sqlite3
path = 'c:/Project rohan/Alpha_Lens/news_cache.db'
conn = sqlite3.connect(path)
c = conn.cursor()
queries = [
    'SELECT name FROM sqlite_master WHERE type="table" ORDER BY name',
    'SELECT COUNT(*) FROM stock_impact',
    'SELECT COUNT(*) FROM stock_impact WHERE base_price>0',
    'SELECT COUNT(*) FROM stock_impact WHERE status NOT IN ("Expired", "Active View")',
    'SELECT COUNT(*) FROM stock_impact WHERE status="Active View"',
    'SELECT COUNT(*) FROM news',
    'SELECT COUNT(*) FROM stock_impact WHERE news_id IS NULL',
    'SELECT DISTINCT status FROM stock_impact',
    'SELECT id, ticker, status, created_at, base_price FROM stock_impact ORDER BY id DESC LIMIT 10'
]
for q in queries:
    try:
        rows = c.execute(q).fetchall()
        print('QUERY:', q)
        print(rows)
    except Exception as err:
        print('ERROR:', q, err)
conn.close()
