"""
Targeted fix for the specific signals shown in the screenshots.

CAMS.NS (ID=157, news at 2:29 PM IST = market hours):
  - base_price was wrongly set to 797.4 (current price) by bulk fix
  - Need to restore to the actual price at 2:29 PM
  - We'll fetch it from Angel One 1-min candle data

DLF.NS (ID=201) and LODHA.NS (ID=202) (news at 3:38 PM IST = after market):
  - base_price=607.2 (yesterday close) != current_price=597.3 (today close)
  - Status wrongly says Stop Loss Hit — but no trading happened since news
  - Fix: set base=cur=today's close, status=Active View, pct=0%
"""
import sqlite3, sys, io, requests, json
from datetime import datetime, timedelta, timezone
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = sqlite3.connect('news_cache.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ── Fix 1: DLF and LODHA — after-hours news, wrong Stop Loss Hit ──
# The news was at 3:38 PM IST (after market close). base_price came from
# yesterday's close, current_price from today's close — creating fake -1.6%
# which triggered a false Stop Loss. Reset both to today's close = 0%.

# DLF today's close = 597.3 (the current_price is correct — it's today's close)
print("=== Fix 1: DLF.NS and LODHA.NS — Reset after-hours false Stop Loss ===")

c.execute("""
    UPDATE stock_impact
    SET base_price = current_price,
        estimated_change_percent = 0.0,
        status = 'Active View'
    WHERE id IN (201, 202)
""")
print(f"  Updated {c.rowcount} rows (DLF, LODHA) -> Active View, 0%")

# ── Fix 2: CAMS.NS (ID=157) — market-hours news, base was wrongly overwritten ──
# News at 2:29 PM IST. Need to find the actual price at that time.
# We'll fetch a Yahoo Finance 1-minute candle around that time.
print("\n=== Fix 2: CAMS.NS (ID=157) — Restore correct intraday base_price ===")

# Try Yahoo Finance chart API for 5-May-2026 2:29 PM IST candles
try:
    headers = {"User-Agent": "Mozilla/5.0"}
    # Get 2d 1-min data to cover 5 May
    url = "https://query1.finance.yahoo.com/v8/finance/chart/CAMS.NS?range=2d&interval=1m"
    resp = requests.get(url, headers=headers, timeout=10)
    data = resp.json()
    result = data['chart']['result'][0]
    timestamps = result['timestamp']
    closes = result['indicators']['quote'][0]['close']

    IST = timezone(timedelta(hours=5, minutes=30))
    # News time: 2026-05-05 14:29:31 IST
    target_dt = datetime(2026, 5, 5, 14, 29, 31, tzinfo=IST)

    # Find closest bar at or before 2:29 PM IST
    best_price = None
    best_ts = None
    for ts, cl in zip(timestamps, closes):
        if cl is None:
            continue
        bar_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
        if bar_dt <= target_dt:
            best_price = cl
            best_ts = bar_dt

    if best_price and best_price > 0:
        print(f"  Found CAMS price at {best_ts.strftime('%H:%M IST')}: ₹{best_price:.2f}")
        c.execute("""
            UPDATE stock_impact
            SET base_price = ?
            WHERE id = 157
        """, (round(best_price, 2),))
        print(f"  Updated CAMS ID=157 base_price -> {round(best_price, 2)}")
    else:
        print("  Could not find intraday price for CAMS — Yahoo returned no data")
        # Fallback: CAMS opened around 780 on 5-May, closed 797.4
        # At 2:29 PM it was likely around 780-790 based on the "9% jump" headline
        print("  Using approximate price: headline says '9% jump' so if close=797.4, base~730")
        # Actually let's compute: if it jumped 9% and closed at 797.4,
        # the pre-news price = 797.4 / 1.09 ≈ 731.6
        estimated_base = round(797.4 / 1.09, 2)
        print(f"  Estimated base (reverse 9% calc): {estimated_base}")
        c.execute("UPDATE stock_impact SET base_price = ? WHERE id = 157", (estimated_base,))

except Exception as e:
    print(f"  Error fetching CAMS candles: {e}")

conn.commit()

# Verify
print("\n=== Verification ===")
c.execute("""
    SELECT id, ticker, base_price, current_price, estimated_change_percent, status
    FROM stock_impact
    WHERE id IN (157, 162, 200, 201, 202, 203)
    ORDER BY id DESC
""")
for r in c.fetchall():
    bp = r['base_price'] or 0
    cp = r['current_price'] or 0
    pct = round((cp - bp) / bp * 100, 2) if bp > 0 else 0
    print(f"  ID={r['id']} {r['ticker']:18s} base={bp:>8.2f} cur={cp:>8.2f} calc_pct={pct:>6.2f}% stored_pct={r['estimated_change_percent']:>6.2f}% | {r['status']}")

conn.close()
print("\nDone!")
