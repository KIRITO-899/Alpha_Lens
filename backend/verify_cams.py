"""Verify CAMS signals specifically."""
import requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

r = requests.get('http://127.0.0.1:5000/api/news/all')
data = r.json()

for n in data.get('news', []):
    stocks = n.get('affected_stocks', [])
    cams = [s for s in stocks if 'CAMS' in s.get('ticker', '')]
    if cams:
        print(f"NEWS: {n['headline'][:70]}")
        print(f"  news_time: {n.get('news_time', 'N/A')}")
        for s in cams:
            print(f"  {s['ticker']} base={s.get('base_price')} cur={s.get('current_price')} diff_pct={s.get('diff_pct')}% | {s.get('status')}")
        print()
