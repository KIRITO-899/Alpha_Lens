"""Verify: stocks should show base_price == current_price (0% change) when market is closed"""
import urllib.request
import json

try:
    resp = urllib.request.urlopen("http://127.0.0.1:5000/api/news/all", timeout=10)
    data = json.loads(resp.read())
    
    mkt_open = data.get('market_open', True)
    news = data.get('news', [])
    print(f"market_open: {mkt_open}")
    print(f"Total articles: {len(news)}")
    
    checked = 0
    wrong = 0
    for article in news:
        stocks = article.get('affected_stocks', [])
        if not stocks:
            continue
        for s in stocks:
            bp = s.get('base_price', 0)
            cp = s.get('current_price', 0)
            if bp and bp > 0:
                change = round(((cp - bp) / bp) * 100, 2)
                if abs(change) > 0.01 and not mkt_open:
                    wrong += 1
                    print(f"  WRONG: {s['ticker']:20s} base={bp} curr={cp} change={change:+.2f}%")
                checked += 1
        if checked >= 30:
            break
    
    if wrong == 0:
        print(f"\nPASS: All {checked} stocks show correct data (0% change when market closed)")
    else:
        print(f"\nFAIL: {wrong}/{checked} stocks still showing non-zero change!")
        
except Exception as e:
    print(f"ERROR: {e}")
