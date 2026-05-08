"""
ROOT FIX: For after-hours signals, the base_price must be the OFFICIAL NSE closing price
of the day the news was published — NOT Angel One's "last tick" LTP which can differ
significantly from the official close.

The official NSE closing price at 3:30 PM is a VWAP calculation, very different from
the last-traded price that Angel One returns. This is why we see 0% — the base was
set from the wrong source.

This script:
1. Finds all after-hours signals (news outside 9:15-15:30 IST)
2. Fetches the official NSE close of the news day from Yahoo Finance 5d/1m
3. Fetches the most recent official NSE close for current_price
4. Recalculates estimated_change_percent
"""
import sqlite3, sys, io, requests
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
IST = timezone(timedelta(hours=5, minutes=30))

# Cache of all 1-min bars per ticker (fetched once)
_bar_cache = {}

def fetch_all_bars(ticker):
    """Fetch 5d 1-min bars from Yahoo Finance for a ticker. Returns sorted list of (datetime, close)."""
    if ticker in _bar_cache:
        return _bar_cache[ticker]
    try:
        h = {"User-Agent": "Mozilla/5.0"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1m"
        r = requests.get(url, headers=h, timeout=10)
        data = r.json()
        result = data['chart']['result'][0]
        tss    = result['timestamp']
        closes = result['indicators']['quote'][0]['close']
        bars = []
        for ts, cl in zip(tss, closes):
            if cl is None:
                continue
            bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
            bars.append((bar_dt, round(float(cl), 2)))
        bars.sort(key=lambda x: x[0])
        _bar_cache[ticker] = bars
        return bars
    except Exception as e:
        print(f"    [fetch error] {ticker}: {e}")
        _bar_cache[ticker] = []
        return []


def get_official_close_on_date(ticker, target_date):
    """
    Get the official NSE closing price for ticker on target_date.
    Uses the 15:28-15:31 IST window (official close window).
    """
    bars = fetch_all_bars(ticker)
    best_p = None
    for bar_dt, cl in bars:
        if bar_dt.date() != target_date:
            continue
        bar_t = bar_dt.hour * 60 + bar_dt.minute
        if (15 * 60 + 28) <= bar_t <= (15 * 60 + 31):
            best_p = cl  # Last one in window
    return best_p


def get_most_recent_close(ticker):
    """Get the most recent 3:30 PM close from Yahoo (last available trading day)."""
    bars = fetch_all_bars(ticker)
    best_p  = None
    best_dt = None
    for bar_dt, cl in bars:
        bar_t = bar_dt.hour * 60 + bar_dt.minute
        if (15 * 60 + 28) <= bar_t <= (15 * 60 + 31):
            best_p  = cl
            best_dt = bar_dt
    return best_p, best_dt


def prev_trading_day(dt_ist):
    """Get the most recent trading day before dt_ist (skip weekends)."""
    d = dt_ist.date() - timedelta(days=1)
    while d.weekday() >= 5:  # Skip weekends
        d -= timedelta(days=1)
    return d


# ── DB ──
conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

rows = c.execute("""
    SELECT si.id, si.ticker, si.base_price, si.current_price,
           si.estimated_change_percent, si.status, n.news_time, n.headline
    FROM stock_impact si
    JOIN news n ON si.news_id = n.id
    WHERE si.status = 'Active View'
    ORDER BY si.id DESC
""").fetchall()

print(f"Processing {len(rows)} active signals...\n")

now_ist  = datetime.now(IST)
last_market_date = now_ist.date()
if now_ist.weekday() >= 5 or now_ist.hour < 9 or (now_ist.hour == 9 and now_ist.minute < 15):
    last_market_date = prev_trading_day(now_ist)

print(f"Most recent trading day: {last_market_date}\n")

fixes = 0

for r in rows:
    try:
        pub_dt = parsedate_to_datetime(r['news_time']).astimezone(IST)
    except:
        continue

    ticker  = r['ticker']
    base    = r['base_price'] or 0
    stored  = r['current_price'] or 0

    pub_date = pub_dt.date()
    pub_t    = pub_dt.hour * 60 + pub_dt.minute
    is_market_hours = (pub_dt.weekday() < 5 and (9*60+15) <= pub_t <= (15*60+30))

    if is_market_hours:
        # Market-hours signals: base is already correct (set from 1-min candle at news time)
        # Just ensure current_price = most recent official close
        recent_close, recent_dt = get_most_recent_close(ticker)
        if recent_close and recent_close > 0 and base > 0:
            new_pct = round((recent_close - base) / base * 100, 2)
            if abs(recent_close - stored) > 0.1 or abs(new_pct - (r['estimated_change_percent'] or 0)) > 0.05:
                print(f"  [MKT] ID={r['id']:>3} {ticker:18s} | base={base:>9.2f} cur_upd: {stored:.2f} → {recent_close:.2f} ({new_pct:+.2f}%)")
                c.execute("UPDATE stock_impact SET current_price=?, estimated_change_percent=? WHERE id=?",
                          (recent_close, new_pct, r['id']))
                fixes += 1
        continue

    # ── AFTER-HOURS SIGNAL ──
    # Step 1: Find the trading day of the news
    # If news was before 9:15 AM on day X, it's pre-market → trading day = X
    # If news was after 15:30 on day X, it's post-market → next trading day is X+1
    if pub_t >= (15*60+30):
        # Post-market: the relevant trading day is the NEXT trading day after pub_date
        news_base_date = pub_date  # base = official close OF THE DAY PUBLISHED (yesterday's close)
    else:
        # Pre-market (e.g., 5:06 AM): base = prev trading day's close (= yesterday's close)
        news_base_date = prev_trading_day(pub_dt)

    # Step 2: Get official NSE close on news_base_date
    official_base = get_official_close_on_date(ticker, news_base_date)

    # Step 3: Get most recent official close for current_price
    recent_close, recent_dt = get_most_recent_close(ticker)

    if not official_base or not recent_close or base <= 0:
        print(f"  [SKIP] ID={r['id']:>3} {ticker:18s} | pub={pub_dt.strftime('%d-%b %H:%M')} base_date={news_base_date} → base_close={'N/A' if not official_base else official_base} recent={'N/A' if not recent_close else recent_close}")
        continue

    new_pct = round((recent_close - official_base) / official_base * 100, 2)
    old_pct = r['estimated_change_percent'] or 0

    changed = abs(official_base - base) > 0.1 or abs(recent_close - stored) > 0.1

    if changed:
        recent_dt_str = recent_dt.strftime('%d-%b') if recent_dt else '?'
        print(f"  [AFT] ID={r['id']:>3} {ticker:18s} | pub={pub_dt.strftime('%d-%b %H:%M')} "
              f"base: {base:.2f}→{official_base:.2f} "
              f"cur: {stored:.2f}→{recent_close:.2f} "
              f"pct: {old_pct:+.2f}%→{new_pct:+.2f}%")
        c.execute("""
            UPDATE stock_impact
            SET base_price=?, current_price=?, estimated_change_percent=?
            WHERE id=?
        """, (official_base, recent_close, new_pct, r['id']))
        fixes += 1
    else:
        print(f"  [OK]  ID={r['id']:>3} {ticker:18s} | pub={pub_dt.strftime('%d-%b %H:%M')} base={official_base:.2f} cur={recent_close:.2f} pct={new_pct:+.2f}%")

conn.commit()
print(f"\n{'='*60}")
print(f"Fixed {fixes} signals total.")

# Show final state for screenshot tickers
print(f"\n=== Verification for screenshot stocks ===")
for ticker in ('SBIN.NS', 'SIEMENS.NS', 'ADANIENT.NS', 'TATAMOTORS.NS', 'ADANIPORTS.NS'):
    rows2 = c.execute("""
        SELECT si.id, si.ticker, si.base_price, si.current_price, si.estimated_change_percent, si.status, n.news_time
        FROM stock_impact si JOIN news n ON si.news_id = n.id
        WHERE si.ticker=? AND si.status='Active View'
        ORDER BY si.id DESC LIMIT 3
    """, (ticker,)).fetchall()
    for r in rows2:
        bp = r['base_price'] or 0
        cp = r['current_price'] or 0
        pct = r['estimated_change_percent'] or 0
        try:
            pub = parsedate_to_datetime(r['news_time']).astimezone(IST)
            ts = pub.strftime('%d-%b %H:%M')
        except:
            ts = "?"
        print(f"  {r['ticker']:18s} [{ts}] base={bp:>9.2f} cur={cp:>9.2f} pct={pct:>+7.2f}% | {r['status']}")

conn.close()
print("\nDone!")
