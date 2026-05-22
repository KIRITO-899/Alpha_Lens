import sys
import os
import json
import sqlite3

sys.path.append(os.path.abspath('backend'))
import app

def get_tickers_with_news():
    conn = sqlite3.connect('news_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker FROM stock_impact LIMIT 10")
    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tickers

print("Tickers in news database:", get_tickers_with_news())

tickers = get_tickers_with_news()
if not tickers:
    print("No tickers found in news database. Testing with mock portfolio TCS...")
    tickers = ["TCS.NS"]

test_ticker = tickers[0]
print(f"Testing with ticker: {test_ticker}")

question = f"What is the latest news and impact for {test_ticker.split('.')[0]}?"
holdings = [{"ticker": test_ticker, "name": test_ticker.split('.')[0]}]

with app.app.test_client() as client:
    res = client.post('/api/portfolio-assistant', json={
        "question": question,
        "holdings": holdings
    })
    print("Status code:", res.status_code)
    data = json.loads(res.get_data(as_text=True))
    print("Response payload:")
    print(json.dumps(data, indent=2))
