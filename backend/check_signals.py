import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT si.id, si.ticker, si.impact, si.base_price, si.current_price,
           si.estimated_change_percent, si.status, si.created_at,
           n.news_time, n.headline
    FROM stock_impact si
    JOIN news n ON si.news_id = n.id
    WHERE si.ticker IN ('CAMS.NS','DLF.NS','LODHA.NS','BANKBARODA.NS','HDFCBANK.NS')
    ORDER BY si.id DESC LIMIT 15
""").fetchall()

print("=== Screenshot Signals ===")
for r in rows:
    print(f"\nID={r['id']} {r['ticker']} | {r['impact']}")
    print(f"  news_time  : {r['news_time']}")
    print(f"  created_at : {r['created_at']}")
    print(f"  base={r['base_price']} cur={r['current_price']} pct={r['estimated_change_percent']}%")
    print(f"  status     : {r['status']}")
    print(f"  headline   : {r['headline'][:70]}")

conn.close()
