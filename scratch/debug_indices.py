import sys
import os
import requests
import json
from datetime import datetime, timezone, timedelta

# Add backend to path so we can import app
sys.path.append(os.path.abspath('backend'))
import app

print("Testing _fetch_nse_index_quotes()...")
try:
    nse = app._fetch_nse_index_quotes()
    print("NSE Response keys:", list(nse.keys()))
    print("NSE Response detail:", json.dumps(nse, indent=2))
except Exception as e:
    print("NSE failed:", e)

print("\nTesting Yahoo Chart API for ^NSEI...")
try:
    symbol = "^NSEI"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=8)
    print("Yahoo status code:", resp.status_code)
    data = resp.json()
    chart_result = data.get('chart', {}).get('result', [{}])[0]
    meta = chart_result.get('meta', {})
    print("Yahoo Meta regularMarketPrice:", meta.get('regularMarketPrice'))
    print("Yahoo Meta previousClose:", meta.get('previousClose'))
except Exception as e:
    print("Yahoo failed:", e)

print("\nTesting get_indices()...")
with app.app.test_request_context():
    res = app.get_indices()
    print("get_indices response:", res.get_data(as_text=True))
