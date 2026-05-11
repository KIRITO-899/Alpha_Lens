"""
backfill_signals.py -- Re-processes all news from last 7 days that has no stock signals.
Uses pure rule-based keyword + macro map (zero API keys needed).
Safe to run while app.py is running.
"""
import sys, os, sqlite3
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import keyword maps and helpers from app (no Flask startup happens here)
from app import (
    BULLISH_KEYWORDS, BEARISH_KEYWORDS,
    is_finance_relevant, _fallback_get_candidate_stocks,
)

DB_PATH = os.path.join(os.path.dirname(__file__), 'news_cache.db')


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn


def get_news_without_signals(limit=300):
    conn = connect()
    c = conn.cursor()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("""
        SELECT n.id, n.headline, n.news_time, n.created_at
        FROM news n
        WHERE n.created_at >= ?
          AND NOT EXISTS (SELECT 1 FROM stock_impact si WHERE si.news_id = n.id)
        ORDER BY n.created_at DESC
        LIMIT ?
    """, (cutoff, limit))
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
    reason = f"Rule-based: {direction} signal from keyword analysis. Score={score}."
    c.execute("""INSERT INTO stock_impact
        (news_id, ticker, impact, estimated_change_percent, view, reason,
         base_price, current_price, confidence_score, technical_context, ensemble_detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (news_id, ticker, direction, 2.5, view, reason, 0.0, 0.0, score,
         '', f'Backfill|Rule:{direction}:{score}', created_at))
    conn.commit()
    conn.close()
    return True


def score_signal(headline, direction):
    """Score 50-90 based on keyword alignment with direction."""
    h = headline.lower()
    bull = sum(1 for kw in BULLISH_KEYWORDS if kw in h)
    bear = sum(1 for kw in BEARISH_KEYWORDS if kw in h)
    if direction == 'BULLISH':
        base = 60 + (bull * 5) - (bear * 3)
    else:
        base = 60 + (bear * 5) - (bull * 3)
    return max(50, min(90, base))


def main():
    print("[Backfill] Rule-based signal backfill starting...")
    articles = get_news_without_signals(limit=300)
    print(f"[Backfill] Found {len(articles)} articles with no signals")

    if not articles:
        print("[Backfill] Nothing to do!")
        return

    total_saved = 0
    total_processed = 0

    for news_id, headline, news_time, created_at in articles:
        if not is_finance_relevant(headline):
            continue
        candidates = _fallback_get_candidate_stocks(headline)
        if not candidates:
            continue
        total_processed += 1
        for ticker, direction in candidates[:3]:  # Max 3 per article
            score = score_signal(headline, direction)
            if score >= 55:
                saved = save_signal(news_id, ticker, direction, score, created_at)
                if saved:
                    total_saved += 1
                    print(f"  + {ticker} {direction} ({score}) | {headline[:60]}")

    print(f"\n[Backfill] Done! {total_processed} articles processed, {total_saved} signals saved.")
    print("[Backfill] Refresh http://localhost:5000 -- stocks should now appear!")


if __name__ == "__main__":
    main()
