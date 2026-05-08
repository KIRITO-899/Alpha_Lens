"""Check MARICO, NAM-INDIA, BSE signals from screenshots."""
import requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

r = requests.get('http://127.0.0.1:5000/api/news/all')
data = r.json()

target_tickers = {'MARICO.NS', 'NAM-INDIA.NS', 'BSE.NS', 'CAMS.NS', 'COALINDIA.NS', 'HEROMOTOCO.NS'}

for n in data.get('news', []):
    stocks = n.get('affected_stocks', [])
    hits = [s for s in stocks if s.get('ticker') in target_tickers]
    if hits:
        print(f"NEWS ({n.get('news_time','?')[:25]}): {n['headline'][:65]}")
        for s in hits:
            print(f"  {s['ticker']:18s} base={s.get('base_price'):>9.2f} cur={s.get('current_price'):>9.2f} diff={s.get('diff_pct'):>6.2f}% | {s.get('status')}")
        print()
