import re

with open('backend/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add imports
if 'from bs4 import BeautifulSoup' not in content:
    content = content.replace('import feedparser', 'import feedparser\nfrom bs4 import BeautifulSoup\nimport concurrent.futures')

# 2. Add RSS_CACHE, SEEN_HEADLINES, and scrape_article_text
if 'RSS_CACHE = ' not in content:
    target_cache_block = ''']

# Global state for scraping optimizations
RSS_CACHE = {url: {'etag': None, 'modified': None} for url in RSS_SOURCES}
SEEN_HEADLINES = set()

def scrape_article_text(url):
    """Fetches the actual article body text (first 3 paragraphs) to give AI better context."""
    if not url or "google.com" in url:
        return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            paragraphs = soup.find_all('p')
            text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50])
            return text[:1500]
    except Exception as e:
        print(f"   [Scrape Error] {url}: {e}")
    return ""

def clean_json(raw_text):'''
    content = content.replace(']\n\ndef clean_json(raw_text):', target_cache_block)

# 3. Replace ai_news_worker Phase 1
old_worker_pattern = r'def ai_news_worker\(\):.*?print\(f"Scraped \{len\(raw_articles\)\} headlines from all sources"\)'

new_worker_start = '''def ai_news_worker():
    global LIVE_NEWS_CACHE, current_key_idx, client, MODEL_NAME, SEEN_HEADLINES
    print("[SYSTEM] Alpha Lens v6.0 AI ENSEMBLE Engine Started!")
    print(f"   Pipeline: RSS -> AI Gatekeeper (Gemini) -> Duplicate Filter -> 7-Model Ensemble (>= 70 score & 5/7 vote)")
    print(f"   Background: Batch Gemini for Aam Janta explanations only")
    print(f"   Settings: Min Confidence={MIN_CONFIDENCE} | R:R = 1.5% stop : 3% target")
    
    # Initialize SEEN_HEADLINES from DB on first run
    try:
        conn = connect_news_db()
        c = conn.cursor()
        c.execute("SELECT headline FROM news ORDER BY created_at DESC LIMIT 1000")
        for row in c.fetchall():
            SEEN_HEADLINES.add(row[0].lower().strip())
        conn.close()
    except Exception as e:
        print(f"   [DB Init Error] {e}")

    def fetch_feed(url):
        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        articles = []
        try:
            cache = RSS_CACHE[url]
            feed = feedparser.parse(url, etag=cache['etag'], modified=cache['modified'])
            if feed.status == 304:
                return [] # Not modified
            
            # Update cache
            if hasattr(feed, 'etag'): RSS_CACHE[url]['etag'] = feed.etag
            if hasattr(feed, 'modified'): RSS_CACHE[url]['modified'] = feed.modified
            
            for entry in feed.entries[:30]:
                pub_time = entry.published if hasattr(entry, 'published') else "Just Now"
                if pub_time and pub_time != "Just Now":
                    try:
                        pub_dt = parsedate_to_datetime(pub_time)
                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                        if pub_dt < stale_cutoff:
                            continue
                    except Exception:
                        pass
                link = entry.link if hasattr(entry, 'link') else None
                articles.append({"headline": entry.title, "time": pub_time, "url": link})
        except Exception as e:
            print(f"   RSS Error for {url}: {e}")
        return articles

    while True:
        # ============================================================
        # PHASE 1: INSTANT — Scrape, Filter, Save, Map (no API calls)
        # ============================================================
        raw_articles = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(RSS_SOURCES)) as executor:
            results = executor.map(fetch_feed, RSS_SOURCES)
            for res in results:
                raw_articles.extend(res)
        
        if raw_articles:
            print(f"Scraped {len(raw_articles)} headlines from all sources")'''

content = re.sub(old_worker_pattern, new_worker_start, content, flags=re.DOTALL)

# 4. Replace the duplicate checker
old_dupe_checker = r'# ── Duplicate check \(check ALL existing headlines, with RETRY for lock handling\) ──.*?if is_dupe:\n                continue'

new_dupe_checker = '''# ── Fast In-Memory Duplicate Check ──
            h_lower = headline.lower().strip()
            if h_lower in SEEN_HEADLINES:
                continue
            SEEN_HEADLINES.add(h_lower)'''

content = re.sub(old_dupe_checker, new_dupe_checker, content, flags=re.DOTALL)

# 5. Inject full body text
old_ai_call = r'# ── 7-MODEL ENSEMBLE AI STOCK MAPPING & EXTRACTION ──\n            candidates = get_candidate_stocks\(headline, client, MODEL_NAME\)'

new_ai_call = '''# ── Full Text Scraping (Context Boost) ──
            body_text = scrape_article_text(article.get('url'))
            ai_input = headline
            if body_text:
                ai_input = f"{headline}\\nContext: {body_text}"
            
            # ── 7-MODEL ENSEMBLE AI STOCK MAPPING & EXTRACTION ──
            candidates = get_candidate_stocks(ai_input, client, MODEL_NAME)'''

content = re.sub(old_ai_call, new_ai_call, content, flags=re.DOTALL)

# Update ensemble.predict to use ai_input
content = content.replace('headline=headline,', 'headline=ai_input,', 1)

with open('backend/app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
