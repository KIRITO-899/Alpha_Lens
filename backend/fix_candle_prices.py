"""Fix CAMS and other signals: set base_price from 1-min candle at news time."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'c:/Project rohan/Alpha_Lens/backend')
from dotenv import load_dotenv
load_dotenv('c:/Project rohan/Alpha_Lens/.env')
import sqlite3, time
import angelone_shim as yf
from datetime import datetime, timedelta, timezone
import pandas as pd

time.sleep(2)

IST = timezone(timedelta(hours=5, minutes=30))
conn = sqlite3.connect('c:/Project rohan/Alpha_Lens/backend/news_cache.db')
c = conn.cursor()

# Get all Active View signals that need fixing
c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price, si.created_at, si.status
    FROM stock_impact si 
    WHERE si.status IN ('Active View', 'Predicted Target Hit', 'Stop Loss Hit')
    AND si.created_at > '2026-05-04'
    ORDER BY si.id
""")
signals = c.fetchall()
print(f"Found {len(signals)} recent signals to check")

fixed = 0
candle_cache = {}  # ticker -> DataFrame of 1-min candles

for row in signals:
    sid, ticker, old_base, curr, created_at, status = row
    
    # Parse created_at as UTC, convert to IST
    try:
        dt_utc = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        dt_ist = dt_utc.astimezone(IST)
    except:
        continue
    
    # Only fix market-hours signals
    if dt_ist.weekday() >= 5:
        continue
    t_min = dt_ist.hour * 60 + dt_ist.minute
    if not (9*60+15 <= t_min <= 15*60+30):
        continue
    
    # Get 1-min candles (cached per ticker)
    if ticker not in candle_cache:
        exchange, token = yf._get_exchange_token(ticker)
        if exchange and token:
            from_dt = datetime.now(timezone.utc) - timedelta(days=2)
            to_dt = datetime.now(timezone.utc)
            df = yf._ao_get_candle(exchange, token, "ONE_MINUTE", from_dt, to_dt)
            if not df.empty:
                df.index = pd.to_datetime(df.index).tz_convert(IST)
                candle_cache[ticker] = df
            else:
                candle_cache[ticker] = pd.DataFrame()
        else:
            candle_cache[ticker] = pd.DataFrame()
    
    df = candle_cache[ticker]
    if df.empty:
        continue
    
    # Find closest candle at or before news time
    close_col = df['Close']
    window_start = dt_ist - timedelta(minutes=5)
    window = close_col[(close_col.index >= window_start) & (close_col.index <= dt_ist)]
    
    if not window.empty:
        correct_base = round(float(window.iloc[-1]), 2)
    else:
        # Try broader: any candle before news time
        past = close_col[close_col.index <= dt_ist]
        if not past.empty:
            correct_base = round(float(past.iloc[-1]), 2)
        else:
            continue
    
    if abs(correct_base - old_base) > 0.5:
        # Get current LTP
        ltp, prev, _, _ = yf._get_cached_quote(ticker)
        ltp = round(float(ltp), 2) if ltp and ltp > 0 else curr
        pct = round((ltp - correct_base) / correct_base * 100, 2) if correct_base > 0 else 0
        
        c.execute("UPDATE stock_impact SET base_price=?, current_price=?, estimated_change_percent=? WHERE id=?",
                  (correct_base, ltp, pct, sid))
        print(f"  {ticker:20s} ID={sid} base {old_base} -> {correct_base} @ {dt_ist.strftime('%H:%M')} IST, curr={ltp}, pct={pct}%")
        fixed += 1

conn.commit()
conn.close()
print(f"\nFixed {fixed} signals with correct 1-minute candle prices.")

# Cleanup
import os
for f in ['test_candle.py']:
    try: os.remove(f'c:/Project rohan/Alpha_Lens/backend/{f}')
    except: pass
