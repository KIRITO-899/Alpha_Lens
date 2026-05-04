"""
Alpha Lens — Win Rate Checker
Reads the last 100 approved signals from the database (stock_impact table)
and evaluates each one against actual price data using yfinance.
No AI API calls needed — signals are already in the DB.

Target: +1.5% | Stop: -3.0%
Scan window: 3 trading days (15-min candles)
"""

import sqlite3
import sys
import os
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import logging
import io
logging.getLogger("yfinance").disabled = True

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ─── CONFIG ───────────────────────────────────────────────────────────────────
DB_PATH     = os.path.join(os.path.dirname(__file__), '..', 'news_cache.db')
TARGET_PCT  =  1.5   # +1.5% to win
STOP_PCT    = -3.0   # -3.0% to lose
LIMIT       = 100    # Last N signals to test (uses all available if fewer)
SCAN_DAYS   = 5      # Calendar days to scan (covers ~3 trading sessions)

# ─── COLORS ───────────────────────────────────────────────────────────────────
GREEN  = ""
RED    = ""
YELLOW = ""
CYAN   = ""
BOLD   = ""
RESET  = ""

# ─── DB QUERY ─────────────────────────────────────────────────────────────────
def fetch_signals(limit=100):
    """Fetch the last N approved signals from stock_impact joined with news."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=15)
        c = conn.cursor()
        c.execute("""
            SELECT
                si.id,
                si.ticker,
                si.impact,
                si.base_price,
                si.confidence_score,
                si.created_at,
                n.headline
            FROM stock_impact si
            JOIN news n ON si.news_id = n.id
            WHERE si.base_price > 0
            ORDER BY si.id DESC
            LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"{RED}DB Error: {e}{RESET}")
        return []

# ─── PRICE SCANNER ────────────────────────────────────────────────────────────
def scan_outcome(ticker, base_price, direction, signal_time_str):
    """
    Downloads 15-min candles and scans High/Low for TARGET or STOP hit.
    Returns: ('TARGET_HIT' | 'STOP_HIT' | 'EXPIRED' | 'NO_DATA', pct, day)
    """
    try:
        # Parse signal time
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                sig_dt = datetime.strptime(signal_time_str, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            return "NO_DATA", 0, 0

        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d", interval="15m")

        if hist.empty:
            return "NO_DATA", 0, 0

        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        hist.index = hist.index.tz_convert(ist)
        sig_dt_ist = sig_dt.astimezone(ist)

        # Candles AFTER the signal
        future = hist[hist.index > sig_dt_ist]
        if future.empty or len(future) < 2:
            return "NO_DATA", 0, 0

        end_scan = sig_dt_ist + timedelta(days=SCAN_DAYS)
        scan = future[future.index <= end_scan]
        if scan.empty:
            return "NO_DATA", 0, 0

        is_bull = "BULL" in direction.upper()

        if is_bull:
            target_price = base_price * (1 + TARGET_PCT / 100)
            stop_price   = base_price * (1 + STOP_PCT  / 100)
        else:
            target_price = base_price * (1 - TARGET_PCT / 100)
            stop_price   = base_price * (1 - STOP_PCT  / 100)

        for i, (idx, candle) in enumerate(scan.iterrows()):
            high = candle["High"]
            low  = candle["Low"]
            hrs  = (idx - sig_dt_ist).total_seconds() / 3600
            day  = 1 if hrs <= 24 else (2 if hrs <= 48 else 3)

            if is_bull:
                t_hit = high >= target_price
                s_hit = low  <= stop_price
            else:
                t_hit = low  <= target_price
                s_hit = high >= stop_price

            if t_hit and s_hit:
                close_pct = (candle["Close"] - base_price) / base_price * 100
                return ("TARGET_HIT" if (is_bull and close_pct >= 0) or (not is_bull and close_pct <= 0)
                        else "STOP_HIT", round(close_pct, 2), day)

            if t_hit:
                pct = (candle["Close"] - base_price) / base_price * 100
                return "TARGET_HIT", round(pct, 2), day

            if s_hit:
                pct = (candle["Close"] - base_price) / base_price * 100
                return "STOP_HIT", round(pct, 2), day

        last_pct = (scan["Close"].iloc[-1] - base_price) / base_price * 100
        return "EXPIRED", round(last_pct, 2), 3

    except Exception as e:
        return "NO_DATA", 0, 0

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}{'='*62}{RESET}")
    print(f"{BOLD}   ALPHA LENS — WIN RATE CHECKER (Last {LIMIT} Signals){RESET}")
    print(f"{BOLD}   Target: +{TARGET_PCT}%  |  Stop: {STOP_PCT}%  |  Window: 3 days{RESET}")
    print(f"{BOLD}{'='*62}{RESET}\n")

    signals = fetch_signals(LIMIT)
    if not signals:
        print(f"{RED}No signals found in the database. Run the app first to generate signals.{RESET}")
        return

    print(f"Found {len(signals)} signals to evaluate...\n")

    stats = {"wins": 0, "losses": 0, "expired": 0, "no_data": 0}
    results_log = []

    for i, (sid, ticker, direction, base_price, conf, created_at, headline) in enumerate(signals):
        print(f"[{i+1}/{len(signals)}] {ticker} {direction} @ Rs.{base_price:.2f}  |  {headline[:50]}...")

        result, pct, day = scan_outcome(ticker, float(base_price), direction, created_at)

        if result == "TARGET_HIT":
            stats["wins"] += 1
            icon = "[WIN]"
        elif result == "STOP_HIT":
            stats["losses"] += 1
            icon = "[LOSS]"
        elif result == "EXPIRED":
            stats["expired"] += 1
            icon = "[EXPIRED]"
        else:
            stats["no_data"] += 1
            icon = "[NO DATA]"

        pct_str = f"{pct:+.2f}%" if result != "NO_DATA" else "—"
        day_str = f"Day {day}" if result not in ("NO_DATA", "EXPIRED") else ""
        print(f"   {icon}  {pct_str}  {day_str}\n")

        results_log.append({
            "ticker": ticker, "direction": direction, "base_price": base_price,
            "result": result, "pct": pct, "day": day, "conf": conf
        })

        time.sleep(0.4)  # Respect yfinance rate limits

    # ─── FINAL REPORT ─────────────────────────────────────────────────────────
    completed = stats["wins"] + stats["losses"]
    win_rate  = round((stats["wins"] / completed) * 100, 1) if completed > 0 else 0

    avg_win  = round(sum(r["pct"] for r in results_log if r["result"] == "TARGET_HIT") / max(stats["wins"],  1), 2)
    avg_loss = round(sum(r["pct"] for r in results_log if r["result"] == "STOP_HIT")   / max(stats["losses"], 1), 2)
    rr_ratio = round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0

    # By direction
    bull_wins  = sum(1 for r in results_log if r["direction"] == "BULLISH" and r["result"] == "TARGET_HIT")
    bull_total = sum(1 for r in results_log if r["direction"] == "BULLISH" and r["result"] in ("TARGET_HIT","STOP_HIT"))
    bear_wins  = sum(1 for r in results_log if r["direction"] == "BEARISH" and r["result"] == "TARGET_HIT")
    bear_total = sum(1 for r in results_log if r["direction"] == "BEARISH" and r["result"] in ("TARGET_HIT","STOP_HIT"))

    if win_rate >= 65:
        rating = f"{GREEN}{BOLD}ELITE{RESET}"
    elif win_rate >= 55:
        rating = f"{CYAN}{BOLD}SOLID{RESET}"
    elif win_rate >= 45:
        rating = f"{YELLOW}{BOLD}MODERATE{RESET}"
    else:
        rating = f"{RED}{BOLD}NEEDS IMPROVEMENT{RESET}"

    print("\n" + "=" * 62)
    print(f"   ALPHA LENS -- FINAL PERFORMANCE REPORT")
    print("=" * 62)
    print(f"  Signals Evaluated  : {len(signals)}")
    print(f"  Resolved Trades    : {completed}  ({stats['wins']} wins | {stats['losses']} losses)")
    print(f"  Expired (no move)  : {stats['expired']}")
    print(f"  No Price Data      : {stats['no_data']}")
    print("-" * 62)
    print(f"  [+] Wins  (Target Hit)  : {stats['wins']}")
    print(f"  [-] Losses (Stop Hit)   : {stats['losses']}")
    print("-" * 62)
    print(f"  WIN RATE                : {win_rate}%   {rating}")
    print(f"  Avg Win                 : +{avg_win}%")
    print(f"  Avg Loss                : {avg_loss}%")
    print(f"  Risk/Reward Ratio       : {rr_ratio}:1")
    print("-" * 62)
    bwr = round(bull_wins/bull_total*100,1) if bull_total > 0 else 0
    bwr2= round(bear_wins/bear_total*100,1) if bear_total > 0 else 0
    print(f"  BULLISH Win Rate   : {bwr}%  ({bull_wins}/{bull_total})")
    print(f"  BEARISH Win Rate   : {bwr2}%  ({bear_wins}/{bear_total})")
    print("=" * 62)

    # Save JSON report
    import json
    out = {
        "generated_at": datetime.now().isoformat(),
        "total_signals": len(signals),
        "resolved": completed,
        "win_rate_pct": win_rate,
        "wins": stats["wins"],
        "losses": stats["losses"],
        "expired": stats["expired"],
        "no_data": stats["no_data"],
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "rr_ratio": rr_ratio,
        "bull_win_rate": bwr,
        "bear_win_rate": bwr2,
        "trades": results_log
    }
    out_path = os.path.join(os.path.dirname(__file__), "win_rate_report.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  📁 Full report saved: {out_path}")

if __name__ == "__main__":
    main()
