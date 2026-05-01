"""
seed_correct_db.py
Seeds the CORRECT news_cache.db (root level = what the server uses)
with fresh RSS headlines from today.
"""
import sqlite3
import feedparser
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# The server runs from Alpha_Lens/ dir so it opens Alpha_Lens/news_cache.db
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'news_cache.db')

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
print("  SEEDING CORRECT DB:", os.path.abspath(DB_PATH))
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL;")
c = conn.cursor()

# Ensure tables exist
c.execute('''CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    headline TEXT NOT NULL,
    news_time TEXT,
    aam_janta_translation TEXT,
    macro_pathway TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
try:
    c.execute("ALTER TABLE news ADD COLUMN category TEXT DEFAULT 'General'")
except:
    pass
c.execute('''CREATE TABLE IF NOT EXISTS stock_impact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER,
    ticker TEXT,
    impact TEXT,
    estimated_change_percent REAL,
    view TEXT,
    reason TEXT,
    base_price REAL,
    current_price REAL,
    status TEXT DEFAULT 'Active View',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(news_id) REFERENCES news(id)
)''')

# Count before
c.execute("SELECT COUNT(*) FROM news")
before = c.fetchone()[0]
print(f"\n[1] News in DB before: {before}")

# Clear stale news older than 7 days
stale = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
c.execute("DELETE FROM stock_impact WHERE news_id IN (SELECT id FROM news WHERE created_at < ?)", (stale,))
c.execute("DELETE FROM news WHERE created_at < ?", (stale,))
deleted = conn.total_changes
conn.commit()
print(f"[2] Deleted {deleted} stale rows (older than 7 days)")

# Check existing headlines to avoid duplication
c.execute("SELECT headline FROM news")
existing = set(row[0] for row in c.fetchall())
print(f"[3] Existing headlines to skip: {len(existing)}")

# Fetch fresh RSS
print("\n[4] Fetching fresh RSS...")
articles = []
stale_cutoff = datetime.now(timezone.utc) - timedelta(days=7)

for url in RSS_SOURCES:
    try:
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries[:30]:
            headline = entry.title.strip()
            pub_time = entry.published if hasattr(entry, 'published') else None
            if pub_time:
                try:
                    pub_dt = parsedate_to_datetime(pub_time)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    if pub_dt < stale_cutoff:
                        continue
                except Exception:
                    pass
            if is_finance_relevant(headline) and headline not in existing:
                articles.append({'headline': headline, 'time': pub_time or 'Just Now'})
                count += 1
        print(f"   {url.split('/')[2][:40]}: {count} new relevant articles")
    except Exception as e:
        print(f"   ERROR [{url[:50]}]: {e}")

# Deduplicate
seen = set()
unique = []
for a in articles:
    if a['headline'] not in seen:
        seen.add(a['headline'])
        unique.append(a)

print(f"\n[5] Unique new articles to insert: {len(unique)}")

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

c.execute("SELECT COUNT(*) FROM news")
after = c.fetchone()[0]
conn.close()

print(f"[6] Inserted {inserted} new articles")
print(f"[7] Total news in DB now: {after}")
print("\nDONE! Refresh http://127.0.0.1:5000")
print("The AI worker will generate stock predictions in ~10-15 min.")
