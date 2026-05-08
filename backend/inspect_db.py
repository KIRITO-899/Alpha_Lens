import sqlite3, glob, os
# Find all .db files
dbs = glob.glob('*.db') + glob.glob('../*.db')
print("Found DBs:", dbs)
for db in dbs:
    try:
        conn = sqlite3.connect(db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"  {db}: {tables}")
        if 'stock_impact' in tables:
            c = conn.execute("SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM stock_impact WHERE base_price > 0")
            row = c.fetchone()
            print(f"    stock_impact rows: {row[0]} | from {row[1]} to {row[2]}")
        if 'news' in tables:
            c = conn.execute("SELECT COUNT(*) FROM news")
            print(f"    news rows: {c.fetchone()[0]}")
        conn.close()
    except Exception as e:
        print(f"  Error {db}: {e}")
