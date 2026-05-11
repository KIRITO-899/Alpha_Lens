"""
backfill_all_missing.py -- Find ALL news IDs without signals and create them.
Works with whatever database the server is using.
"""
import sqlite3, os, sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import BULLISH_KEYWORDS, BEARISH_KEYWORDS, is_finance_relevant, _fallback_get_candidate_stocks

DB_PATH = os.path.join(os.path.dirname(__file__), 'news_cache.db')
print(f"[Backfill] Database: {DB_PATH}")

def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def get_all_news_without_signals():
    conn = connect()
    c = conn.cursor()
    c.execute("""
        SELECT n.id, n.headline, n.created_at
        FROM news n
        WHERE NOT EXISTS (SELECT 1 FROM stock_impact si WHERE si.news_id = n.id)
        ORDER BY n.id ASC
    """)
    rows = c.fetchall()
    conn.close()
    return rows

def save_signal(news_id, ticker, direction, score, created_at):
    conn = connect()
    c = conn.cursor()
    c.execute("SELECT 1 FROM stock_impact WHERE news_id=? AND ticker=?", (news_id, ticker))
    if c.fetchone():
        conn.close()
        return False
    view = 'High Conviction' if score >= 80 else 'Moderate Conviction' if score >= 65 else 'Speculative'
    c.execute("""INSERT INTO stock_impact
        (news_id, ticker, impact, estimated_change_percent, view, reason,
         base_price, current_price, confidence_score, technical_context, ensemble_detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (news_id, ticker, direction, 2.5, view,
         f"Rule-based {direction} signal (score={score}).",
         0.0, 0.0, score, '', f'Backfill|{direction}:{score}', created_at))
    conn.commit()
    conn.close()
    return True

def score_signal(headline, direction):
    h = headline.lower()
    bull = sum(1 for kw in BULLISH_KEYWORDS if kw in h)
    bear = sum(1 for kw in BEARISH_KEYWORDS if kw in h)
    base = 60 + ((bull * 5) - (bear * 3)) if direction == 'BULLISH' else 60 + ((bear * 5) - (bull * 3))
    return max(50, min(90, base))

def main():
    articles = get_all_news_without_signals()
    print(f"[Backfill] {len(articles)} news rows have no signals")

    total_saved = 0
    for news_id, headline, created_at in articles:
        if not is_finance_relevant(headline):
            continue
        candidates = _fallback_get_candidate_stocks(headline)
        for ticker, direction in candidates[:3]:
            score = score_signal(headline, direction)
            if score >= 55 and save_signal(news_id, ticker, direction, score, created_at):
                total_saved += 1

    conn = connect()
    total_sigs = conn.execute("SELECT count(*) FROM stock_impact").fetchone()[0]
    total_news_with_sigs = conn.execute("SELECT count(DISTINCT news_id) FROM stock_impact").fetchone()[0]
    conn.close()

    print(f"\n[Backfill] Done! {total_saved} new signals created.")
    print(f"[Backfill] DB now has {total_sigs} signals covering {total_news_with_sigs} articles.")
    print("[Backfill] Refresh http://localhost:5000 to see stocks!")

if __name__ == "__main__":
    main()
