"""
ROOT FIX: Corrects all wrongly-resolved signals.

For after-hours news signals:
- base_price should be the NEXT TRADING DAY's open price
- The historical check should only start from the next trading day
- Signals that moved UP but are marked "Stop Loss Hit" need to be re-evaluated

This script:
1. Finds all Stop Loss Hit and Target Hit signals
2. For each, fetches the correct base_price (next open for after-hours signals)
3. Re-evaluates the outcome using correct OHLC data
4. Fixes the DB accordingly
"""
import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
import sqlite3
import requests
from datetime import datetime, timezone, timedelta

DB_PATH = 'backend/news_cache.db'
IST = timezone(timedelta(hours=5, minutes=30))

def is_market_hours(dt_ist):
    t = dt_ist.hour * 60 + dt_ist.minute
    return dt_ist.weekday() < 5 and (9 * 60 + 15) <= t <= (15 * 60 + 30)

def fetch_ohlc(ticker, days=20):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={days}d&interval=1d"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        result = resp.json()['chart']['result'][0]
        timestamps = result.get('timestamp', [])
        quote = result['indicators']['quote'][0]
        rows = []
        for ts, o, h, l, c in zip(timestamps,
                                    quote.get('open', []),
                                    quote.get('high', []),
                                    quote.get('low', []),
                                    quote.get('close', [])):
            if o and h and l:
                rows.append((datetime.fromtimestamp(ts, tz=timezone.utc), float(o), float(h), float(l), float(c or 0)))
        return rows
    except Exception as e:
        print(f"  OHLC fetch error for {ticker}: {e}")
        return []

def get_next_open_price(ohlc_rows, signal_date_ist, was_during_market):
    """Get the open price of the next trading session after the signal."""
    for (bar_dt, o, h, l, c) in ohlc_rows:
        bar_date = bar_dt.astimezone(IST).date()
        if was_during_market:
            # For intraday signals, use the signal's own day bar
            if bar_date >= signal_date_ist:
                return o, bar_date
        else:
            # For after-hours signals, use the NEXT day's open
            if bar_date > signal_date_ist:
                return o, bar_date
    return None, None

def evaluate_outcome(ohlc_rows, base_price, next_session_date, is_bullish, target_pct=2.0, stop_pct=1.0):
    """Check OHLC bars from next_session_date onwards for target/stop hits."""
    if not base_price or base_price <= 0:
        return None, None
    
    for (bar_dt, o, h, l, c) in ohlc_rows:
        bar_date = bar_dt.astimezone(IST).date()
        if bar_date < next_session_date:
            continue  # Skip bars before the signal's effective start
        
        h_pct = ((h - base_price) / base_price) * 100
        l_pct = ((l - base_price) / base_price) * 100
        
        if is_bullish:
            if l_pct <= -stop_pct:
                return 'Stop Loss Hit', round(l_pct, 2)
            if h_pct >= target_pct:
                return 'Predicted Target Hit', round(h_pct, 2)
        else:
            if h_pct >= stop_pct:
                return 'Stop Loss Hit', round(h_pct, 2)
            if l_pct <= -target_pct:
                return 'Predicted Target Hit', round(l_pct, 2)
    
    return None, None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Fetch all resolved and active signals from the last 14 days
    fourteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("""
        SELECT si.id, si.ticker, si.impact, si.base_price, si.current_price,
               si.status, si.estimated_change_percent, si.created_at, n.headline
        FROM stock_impact si
        JOIN news n ON si.news_id = n.id
        WHERE si.created_at > ?
        ORDER BY si.created_at DESC
    """, (fourteen_days_ago,))
    rows = c.fetchall()
    
    print(f"Found {len(rows)} signals to re-evaluate...\n")
    
    ohlc_cache = {}
    fixes = []  # (id, new_base_price, new_status, new_est_change)
    
    for row in rows:
        sid = row['id']
        ticker = row['ticker']
        impact = row['impact']
        base_price = row['base_price']
        current_price = row['current_price']
        status = row['status']
        est_change = row['estimated_change_percent']
        created_at = row['created_at']
        headline = row['headline'][:60]
        
        is_bullish = 'bullish' in impact.lower()
        
        try:
            # Parse signal creation time in IST
            created_dt_utc = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            created_dt_ist = created_dt_utc.astimezone(IST)
        except Exception as e:
            print(f"  [!] Date parse error for ID={sid}: {e}")
            continue
        
        was_during_market = is_market_hours(created_dt_ist)
        signal_date_ist = created_dt_ist.date()
        
        # Fetch OHLC (cached per ticker)
        if ticker not in ohlc_cache:
            ohlc_cache[ticker] = fetch_ohlc(ticker, days=20)
        ohlc = ohlc_cache[ticker]
        
        if not ohlc:
            continue
        
        # Get the correct base price (next open for after-hours, same-bar open for intraday)
        next_open, next_session_date = get_next_open_price(ohlc, signal_date_ist, was_during_market)
        
        if next_open and next_open > 0:
            correct_base = round(next_open, 2)
        else:
            correct_base = base_price  # Keep existing if no data
        
        if not next_session_date:
            next_session_date = signal_date_ist  # fallback
        
        # Re-evaluate the outcome using correct base and starting from next session
        new_status, new_diff = evaluate_outcome(ohlc, correct_base, next_session_date, is_bullish)
        
        # If no hit/stop in OHLC, check if signal is expired (>72 hours old)
        if new_status is None:
            age_hours = (datetime.now(timezone.utc) - created_dt_utc).total_seconds() / 3600
            if age_hours >= 72:
                new_status = 'Expired'
                new_diff = round(((current_price - correct_base) / correct_base * 100), 2) if correct_base > 0 else 0
            else:
                new_status = 'Active View'
                new_diff = round(((current_price - correct_base) / correct_base * 100), 2) if correct_base > 0 else 0
        
        base_changed = abs(correct_base - base_price) > 0.01
        status_changed = new_status != status
        diff_changed = abs((new_diff or 0) - (est_change or 0)) > 0.1
        
        if base_changed or status_changed or diff_changed:
            direction = "BULL" if is_bullish else "BEAR"
            print(f"  FIX ID={sid} [{direction}] {ticker}")
            print(f"    Headline: {headline}")
            print(f"    Created: {created_dt_ist.strftime('%Y-%m-%d %H:%M IST')} ({'market hours' if was_during_market else 'AFTER HOURS'})")
            print(f"    Base: {base_price:.2f} -> {correct_base:.2f}")
            print(f"    Status: {status} -> {new_status}")
            print(f"    Est Change: {est_change:.2f}% -> {new_diff:.2f}%")
            print()
            fixes.append((correct_base, new_status, new_diff, sid))
    
    print(f"\n{'='*60}")
    print(f"Total fixes needed: {len(fixes)}")
    
    if fixes:
        confirm = input("\nApply fixes? (y/n): ").strip().lower()
        if confirm == 'y':
            for (new_base, new_status, new_diff, sid) in fixes:
                c.execute("""
                    UPDATE stock_impact 
                    SET base_price=?, status=?, estimated_change_percent=?
                    WHERE id=?
                """, (new_base, new_status, new_diff, sid))
            conn.commit()
            print(f"DONE: Applied {len(fixes)} fixes to database.")
        else:
            print("Skipped.")
    
    conn.close()


if __name__ == '__main__':
    main()
