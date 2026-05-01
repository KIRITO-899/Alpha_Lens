"""
reset_news.py
Clears all stale news older than 7 days from news_cache.db,
then immediately fetches and inserts fresh RSS headlines (no AI needed).
Run while app.py server is NOT running, or with caution while it is.
"""
import sqlite3
import feedparser
import sys
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'backend', 'news_cache.db')

FINANCE_KEYWORDS = [
    'stock', 'share', 'shares', 'market', 'nifty', 'sensex', 'bse', 'nse',
    'rally', 'crash', 'bull', 'bear', 'trade', 'trading', 'etf', 'ipo',
    'dividend', 'earnings', 'profit', 'loss', 'revenue', 'quarter',
    'rbi', 'sebi', 'inflation', 'rate', 'bond', 'rupee', 'crude', 'oil',
    'gold', 'bank', 'nbfc', 'mutual fund', 'buy', 'sell', 'target',
    'upgrade', 'downgrade', 'fii', 'dii', 'fpi', 'result', 'growth',
    'merger', 'acquisition', 'buyback', 'sector', 'pharma', 'auto',
    'realty', 'infra', 'defence', 'power', 'cement', 'fmcg', 'telecom',
    'midcap', 'smallcap', 'largecap', 'index', 'equity', 'gdp', 'export',
    'import', 'tariff', 'corporate', 'company', 'fund', 'investor',
]

RSS_SOURCES = [
    "https://economictimes.indiatimes.com/markets/stocks/news/rssfeeds/2146842.cms",
    "https://economictimes.indiatimes.com/markets/stocks/earnings/rssfeeds/837588974.cms",
    "https://www.moneycontrol.com/rss/buzzingstocks.xml",
    "https://www.livemint.com/rss/markets",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://news.google.com/rss/search?q=indian+stock+market+when:7d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=NSE+BSE+Nifty+Sensex+stocks+when:7d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=india+stocks+earnings+results+when:7d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=indian+economy+RBI+market+when:7d&hl=en-IN&gl=IN&ceid=IN:en",
]

def is_finance_relevant(headline):
    h = headline.lower()
    return any(kw in h for kw in FINANCE_KEYWORDS)

def classify_category(headline):
    h = headline.lower()
    cats = {
        'Finance': ['stock', 'market', 'nifty', 'sensex', 'rbi', 'sebi', 'fund', 'fii', 'bond', 'inflation', 'rate', 'rupee', 'index', 'rally', 'crash'],
        'Business': ['company', 'merger', 'acquisition', 'ipo', 'earnings', 'profit', 'revenue', 'ceo', 'startup', 'dividend', 'buyback'],
        'Technology': ['tech', 'ai ', 'software', 'digital', 'chip', 'data', 'cloud', 'cyber'],
        'Politics': ['government', 'election', 'minister', 'parliament', 'policy', 'bill'],
        'World': ['global', 'us ', 'china', 'trump', 'fed ', 'european', 'war', 'tariff', 'geopolitical'],
    }
    scores = {cat: sum(1 for kw in kws if kw in h) for cat, kws in cats.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'General'

print("=" * 60)
print("  Alpha Lens — News DB Reset & Fresh Seed")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL;")
c = conn.cursor()

# Count before
c.execute("SELECT COUNT(*) FROM news")
before = c.fetchone()[0]
print(f"\n[1] News in DB before cleanup: {before}")

# Delete ALL old news and associated stock impacts
c.execute("DELETE FROM stock_impact")
c.execute("DELETE FROM news")
conn.commit()
print("[2] Cleared all old stale articles from DB.")

# Fetch fresh RSS
print("\n[3] Fetching fresh RSS headlines from all sources...")
articles = []
stale_cutoff = datetime.now(timezone.utc) - timedelta(days=7)

for url in RSS_SOURCES:
    try:
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries[:30]:
            headline = entry.title.strip()
            pub_time = entry.published if hasattr(entry, 'published') else None
            
            # Skip stale articles
            if pub_time:
                try:
                    pub_dt = parsedate_to_datetime(pub_time)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    if pub_dt < stale_cutoff:
                        continue
                except Exception:
                    pass
            
            if is_finance_relevant(headline):
                articles.append({'headline': headline, 'time': pub_time or 'Just Now'})
                count += 1
        print(f"   {url.split('/')[2][:40]}: {count} relevant articles")
    except Exception as e:
        print(f"   RSS Error [{url[:50]}]: {e}")

print(f"\n[4] Total fresh finance articles fetched: {len(articles)}")

# Deduplicate by exact headline
seen = set()
unique = []
for a in articles:
    if a['headline'] not in seen:
        seen.add(a['headline'])
        unique.append(a)
print(f"[5] After deduplication: {len(unique)} unique articles")

# Insert into DB
inserted = 0
for a in unique:
    cat = classify_category(a['headline'])
    try:
        c.execute(
            "INSERT INTO news (headline, news_time, aam_janta_translation, macro_pathway, category) VALUES (?, ?, ?, ?, ?)",
            (a['headline'], a['time'], None, '[]', cat)
        )
        inserted += 1
    except Exception as e:
        print(f"   Insert error: {e}")

conn.commit()
conn.close()

print(f"\n[6] Successfully inserted {inserted} fresh articles into DB!")
print("\nDone! Refresh your browser at http://127.0.0.1:5000")
print("The background AI worker will now add stock impact signals to these articles.")
