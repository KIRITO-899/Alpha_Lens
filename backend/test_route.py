"""Quick test: simulate get_all_news query for news_id 421"""
import sqlite3, json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import _NEWS_DB, connect_news_db

try:
    conn = connect_news_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM news WHERE id = 421")
    row = c.fetchone()
    if row:
        news_item = dict(row)
        print("News item:", news_item.get('id'), news_item.get('headline', '')[:60])
        c.execute("SELECT * FROM stock_impact WHERE news_id = ?", (news_item['id'],))
        raw_stocks = [dict(s) for s in c.fetchall()]
        print(f"Signals for id=421: {len(raw_stocks)}")
        for s in raw_stocks[:3]:
            print(f"  - {s.get('ticker')} {s.get('impact')} status={s.get('status')}")
    else:
        print("No news found with id=421")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    import traceback; traceback.print_exc()
