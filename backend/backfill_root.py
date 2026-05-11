"""
backfill_root.py -- Run from Alpha_Lens/ root to backfill the root news_cache.db
"""
import sys, os, sqlite3
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
os.chdir(os.path.join(ROOT, 'backend'))

from app import (
    BULLISH_KEYWORDS, BEARISH_KEYWORDS,
    is_finance_relevant, _fallback_get_candidate_stocks,
)

# Target the ROOT database
DB_PATH = os.path.join(ROOT, 'news_cache.db')
print(f"[Backfill-Root] Targeting: {DB_PATH}")

def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def get_news_without_signals(limit=500):
    conn = connect()
    c = conn.cursor()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("""
        SELECT n.id, n.headline, n.news_time, n.created_at
        FROM news n
        WHERE NOT EXISTS (SELECT 1 FROM stock_impact si WHERE si.news_id = n.id)
        ORDER BY n.created_at DESC
        LIMIT ?
    """, (limit,))
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
    reason = f"Rule-based: {direction} keyword signal. Score={score}."
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
    h = headline.lower()
    bull = sum(1 for kw in BULLISH_KEYWORDS if kw in h)
    bear = sum(1 for kw in BEARISH_KEYWORDS if kw in h)
    if direction == 'BULLISH':
        base = 60 + (bull * 5) - (bear * 3)
    else:
        base = 60 + (bear * 5) - (bull * 3)
    return max(50, min(90, base))

def main():
    articles = get_news_without_signals(limit=500)
    print(f"[Backfill-Root] Found {len(articles)} articles without signals")

    total_saved = 0
    for news_id, headline, news_time, created_at in articles:
        if not is_finance_relevant(headline):
            continue
        candidates = _fallback_get_candidate_stocks(headline)
        if not candidates:
            continue
        for ticker, direction in candidates[:3]:
            score = score_signal(headline, direction)
            if score >= 55:
                saved = save_signal(news_id, ticker, direction, score, created_at)
                if saved:
                    total_saved += 1

    print(f"[Backfill-Root] Done. {total_saved} signals saved to root DB.")

if __name__ == "__main__":
    main()
