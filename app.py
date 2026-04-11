from flask import Flask, render_template, request, jsonify, session
import sqlite3
import secrets
import random
import threading
import time
import json
from werkzeug.security import generate_password_hash
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import feedparser
from google import genai
from google.genai import types
import yfinance as yf
import logging
from email.utils import parsedate_to_datetime
yf.set_tz_cache_location("venv/yf_cache")
logger = logging.getLogger('yfinance')
logger.disabled = True
logger.propagate = False

from datetime import datetime, timedelta, timezone
from technical_analysis import (
    get_stock_technical_context,
    format_technical_context_for_prompt,
    get_market_regime
)
from prediction_models import EnsemblePredictor

app = Flask(__name__, template_folder='.')
app.secret_key = "super_secret_alpha_lens_key"

# Minimum AI confidence to accept a prediction
MIN_CONFIDENCE = 65

import performance_report

# In-memory store for OTPs
OTP_STORE = {}
SENDGRID_API_KEY = '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'

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def connect_news_db():
    conn = sqlite3.connect('news_cache.db', timeout=20.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_news_db():
    conn = connect_news_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT NOT NULL,
            news_time TEXT,
            aam_janta_translation TEXT,
            macro_pathway TEXT, -- Stored as JSON string
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        c.execute("ALTER TABLE news ADD COLUMN category TEXT DEFAULT 'General'")
    except sqlite3.OperationalError:
        pass
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_impact (
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
        )
    ''')
    try:
        c.execute("ALTER TABLE stock_impact ADD COLUMN confidence_score INTEGER DEFAULT 80")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE stock_impact ADD COLUMN technical_context TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE stock_impact ADD COLUMN ensemble_detail TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
        
    c.execute('''
        CREATE TABLE IF NOT EXISTS historical_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT,
            ticker TEXT,
            direction TEXT,      -- BULLISH or BEARISH
            outcome TEXT,        -- HIT or MISS
            change_pct REAL,     -- actual change %
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()
init_news_db()

# ==========================================
# LIVE AI NEWS ENGINE (LiveMint, ET, MoneyControl)
# ==========================================
# We no longer use in-memory cache for news, but we keep it here just in case.
LIVE_NEWS_CACHE = []

# Your Gemini API Keys for rotation
API_KEYS = [
    "AIzaSyABS1FGUxLRNcekIfquMcIKcGVjKd-bGq4",
    "AIzaSyCt_GQ1Z39bpkIZMjRZtjmyx-zjxqiFlUw",
    "AIzaSyCUJbHzWvCYzokef_NyXKNWQ6ywniO-wb4",
    "AIzaSyA6En5i8Bpr6_lPKWSMecchwRfHruHw0tU"
]
current_key_idx = 0
client = genai.Client(api_key=API_KEYS[current_key_idx])
MODEL_NAME = 'gemini-2.5-flash'

# Top Tier Indian Financial RSS Feeds + Google News for 4-day history
RSS_SOURCES = [
    "https://economictimes.indiatimes.com/markets/stocks/news/rssfeeds/2146842.cms",
    "https://economictimes.indiatimes.com/markets/stocks/earnings/rssfeeds/837588974.cms",
    "https://www.moneycontrol.com/rss/buzzingstocks.xml",
    "https://www.livemint.com/rss/markets",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    # Google News RSS — past 4 days of Indian market news (instant historical backfill)
    "https://news.google.com/rss/search?q=indian+stock+market+when:4d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=NSE+BSE+Nifty+Sensex+stocks+when:4d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=india+stocks+earnings+results+when:4d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=indian+economy+RBI+market+when:4d&hl=en-IN&gl=IN&ceid=IN:en",
]

def clean_json(raw_text):
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
    return json.loads(cleaned.strip())

# ==========================================
# KEYWORD FILTER — fast relevance check
# ==========================================
FINANCE_KEYWORDS = [
    'stock', 'share', 'shares', 'market', 'nifty', 'sensex', 'bse', 'nse',
    'rally', 'crash', 'bull', 'bear', 'trade', 'trading', 'etf', 'ipo', 'fpo',
    'dividend', 'earnings', 'profit', 'loss', 'revenue', 'quarter',
    'q1', 'q2', 'q3', 'q4', 'rbi', 'sebi', 'inflation', 'rate', 'bond',
    'rupee', 'crude', 'oil', 'gold', 'bank', 'nbfc', 'mutual fund',
    'buy', 'sell', 'target', 'upgrade', 'downgrade', 'fii', 'dii', 'fpi',
    'block deal', 'bulk deal', 'merger', 'acquisition', 'buyback', 'delisting',
    'rebound', 'correction', 'breakout', 'support', 'resistance',
    'sector', 'pharma', 'auto', 'realty', 'infra', 'defence', 'power',
    'cement', 'fmcg', 'telecom', 'midcap', 'smallcap', 'largecap',
    'result', 'growth', 'margin', 'ebitda', 'pat', 'eps',
    'investor', 'portfolio', 'fund', 'index', 'return', 'equity',
    'debt', 'credit', 'loan', 'interest', 'fiscal', 'gdp',
    'export', 'import', 'tariff', 'manufacturing', 'corporate', 'company',
]

def is_finance_relevant(headline):
    h = headline.lower()
    return any(kw in h for kw in FINANCE_KEYWORDS)

# ==========================================
# SENTIMENT KEYWORDS — bullish/bearish rules
# ==========================================
BULLISH_KEYWORDS = [
    'rise', 'rises', 'rising', 'rally', 'rallies', 'surge', 'surges',
    'jump', 'jumps', 'gain', 'gains', 'gained', 'up ', 'high', 'highs',
    'record', 'soar', 'soars', 'zoom', 'zooms', 'profit', 'growth',
    'upgrade', 'outperform', 'buy', 'bullish', 'positive', 'strong',
    'beat', 'beats', 'exceed', 'boost', 'rebound', 'recovery', 'breakout',
    'dividend', 'buyback', 'expansion', 'robust', 'stellar', 'doubles',
    'optimistic', 'upside', 'winner', 'outpace', 'top pick',
]

BEARISH_KEYWORDS = [
    'fall', 'falls', 'falling', 'drop', 'drops', 'crash', 'crashes',
    'plunge', 'plunges', 'decline', 'declines', 'declined', 'down ', 'low',
    'lows', 'sink', 'sinks', 'tumble', 'tumbles', 'loss', 'losses',
    'downgrade', 'underperform', 'sell', 'bearish', 'negative', 'weak',
    'miss', 'misses', 'cut', 'cuts', 'slash', 'concern', 'fear',
    'warning', 'ban', 'penalty', 'fine', 'fraud', 'scam', 'debt',
    'default', 'flee', 'exit', 'outflow', 'worst', 'slump',
]

# ==========================================
# CATEGORY CLASSIFICATION — rule-based
# ==========================================
CATEGORY_KEYWORDS = {
    'Finance': ['stock', 'market', 'nifty', 'sensex', 'rbi', 'sebi', 'fund', 'fii', 'dii', 'bond', 'yield', 'inflation', 'rate', 'rupee', 'forex', 'index', 'rally', 'crash', 'bull', 'bear'],
    'Business': ['company', 'merger', 'acquisition', 'ipo', 'earnings', 'profit', 'revenue', 'ceo', 'board', 'startup', 'valuation', 'q1', 'q2', 'q3', 'q4', 'quarter', 'result', 'dividend', 'buyback'],
    'Technology': ['tech', 'ai ', 'software', 'digital', 'chip', 'semiconductor', 'data', 'cloud', 'cyber', 'app ', 'gadget'],
    'Politics': ['government', 'election', 'minister', 'parliament', 'policy', 'modi', 'bjp', 'congress', 'bill ', 'political'],
    'World': ['global', 'us ', 'china', 'trump', 'fed ', 'european', 'war', 'tariff', 'trade war', 'geopolitical', 'iran', 'russia'],
}

def classify_category(headline):
    h = headline.lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in h)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'General'

# ==========================================
# RULE-BASED STOCK MAPPING — instant, no AI
# ==========================================
import re

STOCK_KEYWORD_MAP = {
    # NIFTY 50
    'reliance': 'RELIANCE.NS', 'reliance industries': 'RELIANCE.NS',
    'tcs': 'TCS.NS', 'tata consultancy': 'TCS.NS',
    'infosys': 'INFY.NS', 'infy': 'INFY.NS',
    'hdfc bank': 'HDFCBANK.NS',
    'icici bank': 'ICICIBANK.NS',
    'sbi ': 'SBIN.NS', 'state bank': 'SBIN.NS',
    'bharti airtel': 'BHARTIARTL.NS', 'airtel': 'BHARTIARTL.NS',
    'hindustan unilever': 'HINDUNILVR.NS', 'hul ': 'HINDUNILVR.NS',
    'itc ': 'ITC.NS',
    'kotak mahindra': 'KOTAKBANK.NS', 'kotak bank': 'KOTAKBANK.NS',
    'larsen': 'LT.NS', 'l&t ': 'LT.NS',
    'axis bank': 'AXISBANK.NS',
    'bajaj finance': 'BAJFINANCE.NS',
    'bajaj finserv': 'BAJAJFINSV.NS',
    'maruti': 'MARUTI.NS', 'maruti suzuki': 'MARUTI.NS',
    'asian paints': 'ASIANPAINT.NS',
    'titan ': 'TITAN.NS', 'titan company': 'TITAN.NS',
    'sun pharma': 'SUNPHARMA.NS', 'sun pharmaceutical': 'SUNPHARMA.NS',
    'wipro': 'WIPRO.NS',
    'hcl tech': 'HCLTECH.NS', 'hcl technologies': 'HCLTECH.NS',
    'power grid': 'POWERGRID.NS',
    'ntpc': 'NTPC.NS',
    'tata motors': 'TATAMOTORS.NS',
    'tata steel': 'TATASTEEL.NS',
    'mahindra': 'M&M.NS', 'm&m': 'M&M.NS',
    'adani enterprises': 'ADANIENT.NS', 'adani ent': 'ADANIENT.NS',
    'adani ports': 'ADANIPORTS.NS',
    'adani green': 'ADANIGREEN.NS',
    'adani power': 'ADANIPOWER.NS',
    'ultratech': 'ULTRACEMCO.NS', 'ultratech cement': 'ULTRACEMCO.NS',
    'nestle india': 'NESTLEIND.NS', 'nestle': 'NESTLEIND.NS',
    'tech mahindra': 'TECHM.NS',
    'indusind bank': 'INDUSINDBK.NS', 'indusind': 'INDUSINDBK.NS',
    'grasim': 'GRASIM.NS',
    'bajaj auto': 'BAJAJ-AUTO.NS',
    'cipla': 'CIPLA.NS',
    'dr reddy': 'DRREDDY.NS', 'dr. reddy': 'DRREDDY.NS',
    'hero motocorp': 'HEROMOTOCO.NS', 'hero moto': 'HEROMOTOCO.NS',
    'coal india': 'COALINDIA.NS',
    'ongc': 'ONGC.NS',
    'bpcl': 'BPCL.NS', 'bharat petroleum': 'BPCL.NS',
    'divis lab': 'DIVISLAB.NS',
    'britannia': 'BRITANNIA.NS',
    'eicher motors': 'EICHERMOT.NS', 'royal enfield': 'EICHERMOT.NS',
    'apollo hospital': 'APOLLOHOSP.NS',
    'tata consumer': 'TATACONSUM.NS',
    'sbi life': 'SBILIFE.NS',
    'hdfc life': 'HDFCLIFE.NS',
    'shriram finance': 'SHRIRAMFIN.NS',
    'bhel': 'BHEL.NS',
    'jsw steel': 'JSWSTEEL.NS',
    'hindalco': 'HINDALCO.NS',
    # Popular Mid/Small Caps
    'muthoot finance': 'MUTHOOTFIN.NS', 'muthoot fin': 'MUTHOOTFIN.NS', 'muthoot': 'MUTHOOTFIN.NS',
    'aurobindo pharma': 'AUROPHARMA.NS', 'aurobindo': 'AUROPHARMA.NS',
    'hpcl': 'HINDPETRO.NS', 'hindustan petroleum': 'HINDPETRO.NS',
    'ioc': 'IOC.NS', 'indian oil': 'IOC.NS',
    'bel': 'BEL.NS', 'bharat electronics': 'BEL.NS',
    'hal': 'HAL.NS', 'hindustan aeronautics': 'HAL.NS',
    'solar industries': 'SOLARINDS.NS',
    'vodafone idea': 'IDEA.NS',
    'godfrey phillips': 'GODFRYPHLP.NS', 'godfrey': 'GODFRYPHLP.NS',
    'tejas network': 'TEJASNET.NS',
    'bandhan bank': 'BANDHANBNK.NS',
    'manappuram': 'MANAPPURAM.NS',
    'zomato': 'ZOMATO.NS',
    'paytm': 'PAYTM.NS', 'one97': 'PAYTM.NS',
    'nykaa': 'NYKAA.NS',
    'delhivery': 'DELHIVERY.NS',
    'vedanta': 'VEDL.NS',
    'jindal steel': 'JINDALSTEL.NS',
    'tata power': 'TATAPOWER.NS',
    'tata elxsi': 'TATAELXSI.NS',
    'ltimindtree': 'LTIM.NS', 'lti mindtree': 'LTIM.NS',
    'pnb': 'PNB.NS', 'punjab national': 'PNB.NS',
    'bank of baroda': 'BANKBARODA.NS',
    'canara bank': 'CANBK.NS',
    'idbi bank': 'IDBI.NS',
    'federal bank': 'FEDERALBNK.NS',
    'yes bank': 'YESBANK.NS',
    'irctc': 'IRCTC.NS',
    'irfc': 'IRFC.NS',
    'rvnl': 'RVNL.NS', 'rail vikas': 'RVNL.NS',
    'nhpc': 'NHPC.NS',
    'suzlon': 'SUZLON.NS', 'suzlon energy': 'SUZLON.NS',
    'tata chemicals': 'TATACHEM.NS',
    'godrej consumer': 'GODREJCP.NS', 'godrej': 'GODREJCP.NS',
    'pidilite': 'PIDILITIND.NS',
    'havells': 'HAVELLS.NS',
    'siemens': 'SIEMENS.NS',
    'abb india': 'ABB.NS',
    'page industries': 'PAGEIND.NS',
    'dmart': 'DMART.NS', 'avenue supermarts': 'DMART.NS',
    'biocon': 'BIOCON.NS',
    'lupin': 'LUPIN.NS',
    'torrent pharma': 'TORNTPHARM.NS',
    'jubilant food': 'JUBLFOOD.NS',
    'indigo': 'INDIGO.NS', 'interglobe': 'INDIGO.NS',
    'spicejet': 'SPICEJET.NS',
    'dixon': 'DIXON.NS', 'dixon tech': 'DIXON.NS',
    'polycab': 'POLYCAB.NS',
    'persistent': 'PERSISTENT.NS', 'persistent systems': 'PERSISTENT.NS',
    'coforge': 'COFORGE.NS',
    'mphasis': 'MPHASIS.NS',
    'max health': 'MAXHEALTH.NS', 'max healthcare': 'MAXHEALTH.NS',
    'motherson': 'MOTHERSON.NS',
    'srf': 'SRF.NS',
    'pi industries': 'PIIND.NS',
    'cholamandalam': 'CHOLAFIN.NS',
    'voltas': 'VOLTAS.NS',
    'bharat forge': 'BHARATFORG.NS',
    'exide': 'EXIDEIND.NS',
    'amara raja': 'AMARAJABAT.NS',
    'marico': 'MARICO.NS',
    'dabur': 'DABUR.NS',
    'colgate': 'COLPAL.NS',
    'acc cement': 'ACC.NS', 'acc ': 'ACC.NS',
    'ambuja': 'AMBUJACEM.NS', 'ambuja cement': 'AMBUJACEM.NS',
    'shree cement': 'SHREECEM.NS',
    'dalmia bharat': 'DALBHARAT.NS',
    'hatsun agro': 'HATSUN.NS', 'hatsun': 'HATSUN.NS',
}

# ==========================================
# MACRO & SECTOR IMPACT MAP — 2nd order effects
# ==========================================
MACRO_IMPACT_MAP = {
    'crude oil rise': [('ONGC.NS', 'BULLISH'), ('BPCL.NS', 'BEARISH'), ('ASIANPAINT.NS', 'BEARISH')],
    'crude oil crash': [('ONGC.NS', 'BEARISH'), ('BPCL.NS', 'BULLISH'), ('ASIANPAINT.NS', 'BULLISH')],
    'fii selling': [('HDFCBANK.NS', 'BEARISH'), ('ICICIBANK.NS', 'BEARISH'), ('RELIANCE.NS', 'BEARISH')],
    'fii buying': [('HDFCBANK.NS', 'BULLISH'), ('ICICIBANK.NS', 'BULLISH'), ('RELIANCE.NS', 'BULLISH')],
    'rate hike': [('DLF.NS', 'BEARISH'), ('LODHA.NS', 'BEARISH'), ('SBIN.NS', 'BULLISH')],
    'rate cut': [('DLF.NS', 'BULLISH'), ('LODHA.NS', 'BULLISH'), ('SBIN.NS', 'BEARISH')],
    'defense budget': [('HAL.NS', 'BULLISH'), ('BEL.NS', 'BULLISH'), ('MAZDOCK.NS', 'BULLISH')],
    'railway budget': [('RVNL.NS', 'BULLISH'), ('IRFC.NS', 'BULLISH'), ('IRCTC.NS', 'BULLISH')],
    'pharma sector rally': [('SUNPHARMA.NS', 'BULLISH'), ('CIPLA.NS', 'BULLISH'), ('DRREDDY.NS', 'BULLISH')],
    'it sector rally': [('INFY.NS', 'BULLISH'), ('TCS.NS', 'BULLISH'), ('WIPRO.NS', 'BULLISH')],
}

def get_candidate_stocks(headline):
    """Finds candidate stock tickers from headline via direct name or macro effects."""
    h = ' ' + headline.lower() + ' '
    candidates = {}
    
    # 1. Direct Stock Mentions
    for keyword, ticker in sorted(STOCK_KEYWORD_MAP.items(), key=lambda x: -len(x[0])):
        if keyword in h and ticker not in candidates:
            # Basic sentiment guess as starting point
            bull_score = sum(1 for kw in BULLISH_KEYWORDS if kw in h)
            bear_score = sum(1 for kw in BEARISH_KEYWORDS if kw in h)
            impact = 'BULLISH' if bull_score >= bear_score else 'BEARISH'
            candidates[ticker] = impact

    # 2. Macro/Sector Mentions
    for macro_kw, effects in MACRO_IMPACT_MAP.items():
        if macro_kw in h:
            for ticker, impact in effects:
                if ticker not in candidates:
                    candidates[ticker] = impact

    # Maximum 3 candidates to avoid noise
    return list(candidates.items())[:3]


# ==========================================
# V3 INSTANT NEWS ENGINE — Two-Phase Pipeline
# ==========================================
def ai_news_worker():
    global LIVE_NEWS_CACHE, current_key_idx, client, MODEL_NAME
    print("[SYSTEM] Alpha Lens v4.0 ENSEMBLE Engine Started!")
    print(f"   Pipeline: RSS -> Keyword Filter -> Duplicate Filter -> Macro Map -> 5-Model Ensemble (Requires >= 70% and 3/5 vote)")
    print(f"   Background: Batch Gemini for Aam Janta explanations only")
    print(f"   Settings: Min Confidence={MIN_CONFIDENCE}")
    
    while True:
        # ============================================================
        # PHASE 1: INSTANT — Scrape, Filter, Save, Map (no API calls)
        # ============================================================
        raw_articles = []
        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=5)
        for url in RSS_SOURCES:
            try:
                feed = feedparser.parse(url)
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
                    raw_articles.append({"headline": entry.title, "time": pub_time})
            except Exception as e:
                print(f"   RSS Error: {e}")
        
        print(f"Scraped {len(raw_articles)} headlines from all sources")
        
        # STEP 1: Keyword Filter
        relevant = [a for a in raw_articles if is_finance_relevant(a['headline'])]
        print(f"Keyword Filter: {len(relevant)}/{len(raw_articles)} finance-relevant")
        
        # Get market regime for technical filters
        market_regime = get_market_regime()
        
        # STEP 2: Duplicate Filter + Instant Save + Stock Mapping
        new_article_ids = []
        conn = connect_news_db()
        c = conn.cursor()
        
        for article in relevant:
            headline = article['headline']
            
            # Duplicate check
            c.execute("SELECT id FROM news WHERE headline = ?", (headline,))
            if c.fetchone():
                continue
            
            # Rule-based category
            category = classify_category(headline)
            
            # INSTANT SAVE — headline goes to DB immediately (aam_janta_translation = NULL)
            c.execute('''INSERT INTO news (headline, news_time, aam_janta_translation, macro_pathway, category)
                VALUES (?, ?, ?, ?, ?)''',
                (headline, article['time'], None, '[]', category))
            news_id = c.lastrowid
            
            # 5-MODEL ENSEMBLE STOCK MAPPING
            candidates = get_candidate_stocks(headline)
            ensemble = EnsemblePredictor()
            saved = 0
            
            for ticker, base_direction in candidates:
                # 1. Fetch fast intraday price (fixes the zero-change bug)
                base_price = 0.0
                try:
                    tick_data = yf.Ticker(ticker)
                    hist = tick_data.history(period='1d', interval='1m')
                    if not hist.empty:
                        base_price = round(hist['Close'].iloc[-1], 2)
                    else:
                        hist_5d = tick_data.history(period='5d')
                        if not hist_5d.empty:
                            base_price = round(hist_5d['Close'].iloc[-1], 2)
                except:
                    base_price = 0.0
                    
                if base_price <= 0:
                    continue  # Skip if we can't reliably get the current price
                    
                # 2. Get tech context
                tech_data = get_stock_technical_context(ticker)
                tech_context_str = json.dumps(tech_data) if tech_data else ""
                
                # 3. Predict using 5-Model Ensemble
                result = ensemble.predict(
                    headline=headline,
                    ticker=ticker,
                    direction=base_direction,
                    tech_data=tech_data,
                    market_regime=market_regime,
                    db_connect_fn=connect_news_db,
                    min_score=MIN_CONFIDENCE
                )
                
                # 4. Save if highly confident (ensemble approved)
                if result['approved']:
                    view = 'High Conviction' if result['final_score'] >= 85 else 'Moderate Conviction'
                    reason = f"Ensemble Score: {result['final_score']} ({result['models_agreeing']}/5 models approve). Expected directional breakout."
                    c.execute('''INSERT INTO stock_impact 
                        (news_id, ticker, impact, estimated_change_percent, view, reason, base_price, current_price, confidence_score, technical_context, ensemble_detail)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (news_id, ticker, result['direction'], 2.5,
                         view, reason, base_price, base_price, result['final_score'], tech_context_str, result['detail']))
                    saved += 1
            
            new_article_ids.append({'id': news_id, 'headline': headline})
            if saved > 0:
                print(f"   [+] ENSEMBLE APPROVED: {headline[:45]}... ({saved} alpha signals)")
        
        conn.commit()
        conn.close()
        
        print(f"PHASE 1 DONE: {len(new_article_ids)} new headlines saved INSTANTLY to database!")
        
        # ============================================================
        # PHASE 2: BACKGROUND — Batch Gemini for explanations only
        # ============================================================
        # Find all articles missing AI explanation
        conn = connect_news_db()
        c = conn.cursor()
        c.execute("SELECT id, headline FROM news WHERE aam_janta_translation IS NULL ORDER BY created_at DESC LIMIT 100")
        pending_articles = [{'id': r[0], 'headline': r[1]} for r in c.fetchall()]
        conn.close()
        
        if pending_articles:
            print(f"[Phase 2] Batch AI explanations for {len(pending_articles)} articles (5 per API call)...")
            
            # Process in batches of 5 headlines per single Gemini call
            for i in range(0, len(pending_articles), 5):
                batch = pending_articles[i:i+5]
                headlines_text = "\n".join([f"{j+1}. {a['headline']}" for j, a in enumerate(batch)])
                
                prompt = f"""You are a financial journalist writing for everyday Indians.
For each headline below, provide:
1. "aam_janta_translation": A 2-sentence explanation in simple language about what this means for common people.
2. "macro_pathway": A 4-step chain showing the macro impact flow.

Headlines:
{headlines_text}

Output STRICT valid JSON array:
[
  {{
    "index": 1,
    "aam_janta_translation": "Simple 2-sentence explanation for common people.",
    "macro_pathway": ["Trigger Event", "Direct Impact", "Ripple Effect", "End Result"]
  }}
]"""
                
                success = False
                retries = 0
                while not success and retries < len(API_KEYS):
                    try:
                        resp = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json"
                            )
                        )
                        analyses = clean_json(resp.text)
                        if not isinstance(analyses, list):
                            analyses = [analyses]
                        
                        conn = connect_news_db()
                        c = conn.cursor()
                        for analysis in analyses:
                            idx = analysis.get('index', 0) - 1
                            if 0 <= idx < len(batch):
                                news_id = batch[idx]['id']
                                c.execute('''UPDATE news SET aam_janta_translation = ?, macro_pathway = ? WHERE id = ?''',
                                    (analysis.get('aam_janta_translation', 'Analysis complete.'),
                                     json.dumps(analysis.get('macro_pathway', [])),
                                     news_id))
                        conn.commit()
                        conn.close()
                        
                        print(f"   [+] Batch {i//5 + 1}: Explained {len(batch)} articles in 1 API call")
                        success = True
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "429" in error_msg or "quota" in error_msg:
                            print(f"   [!] API Quota Reached. Swapping keys...")
                            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                            client = genai.Client(api_key=API_KEYS[current_key_idx])
                            time.sleep(2)
                            retries += 1
                        else:
                            print(f"   [-] Batch Gemini Error: {str(e)[:80]}")
                            break
                
                if not success:
                    print(f"   [-] Failed batch {i//5 + 1} after {retries} retries")
                
                time.sleep(2)  # Small delay between batches
        
        # Clean up old news (older than 4 days)
        try:
            conn = connect_news_db()
            c = conn.cursor()
            four_days_ago = (datetime.now(timezone.utc) - timedelta(days=4)).strftime('%Y-%m-%d %H:%M:%S')
            c.execute("DELETE FROM stock_impact WHERE news_id IN (SELECT id FROM news WHERE created_at < ?)", (four_days_ago,))
            c.execute("DELETE FROM news WHERE created_at < ?", (four_days_ago,))
            conn.commit()
            conn.close()
        except Exception as e:
            print("DB Cleanup Error:", e)
            
        # Performance report
        try:
            import performance_report
            print("\n" + "="*60)
            print(" END OF CYCLE — PERFORMANCE REPORT:")
            print("="*60)
            performance_report.run_performance_check()
        except Exception as e:
            print("Performance Report Error:", e)
            
        time.sleep(600)

def yfinance_worker():
    print("YFinance Live Price Engine v2.1 Started. Asymmetric Thresholds + Time Expiry Active...")
    while True:
        try:
            conn = connect_news_db()
            c = conn.cursor()
            # Fetch active views from last 3 days
            three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
            c.execute("SELECT id, news_id, ticker, base_price, impact, created_at FROM stock_impact WHERE status = 'Active View' AND created_at > ?", (three_days_ago,))
            active_stocks = c.fetchall()
            
            for row in active_stocks:
                stock_id, news_id, ticker, base_price, impact, created_at_str = row
                try:
                    tick_data = yf.Ticker(ticker)
                    current_price = None
                    
                    # PRIMARY: Use 1-minute intraday history for fresh live price
                    try:
                        hist = tick_data.history(period='1d', interval='1m')
                        if not hist.empty:
                            current_price = float(hist['Close'].iloc[-1])
                    except Exception:
                        pass
                    
                    # FALLBACK 1: Use 5-day daily history (works when market is closed)
                    if current_price is None:
                        try:
                            hist = tick_data.history(period='5d')
                            if not hist.empty:
                                current_price = float(hist['Close'].iloc[-1])
                        except Exception:
                            pass
                    
                    # FALLBACK 2: Use fast_info as last resort
                    if current_price is None:
                        current_price = tick_data.fast_info.last_price
                    
                    if current_price is None or current_price <= 0:
                        continue
                    
                    diff_percent = ((current_price - base_price) / base_price) * 100
                    
                    new_status = 'Active View'
                    impact_lower = impact.lower()
                    is_bullish = 'bullish' in impact_lower
                    
                    # ASYMMETRIC thresholds: 1.5% target, 3% stop (wide stop = breathing room)
                    target_pct = 1.5
                    stop_pct = 3.0
                    
                    if is_bullish:
                        if diff_percent >= target_pct:
                            new_status = 'Predicted Target Hit'
                        elif diff_percent <= -stop_pct:
                            new_status = 'Reacted Against Prediction'
                    else: # bearish
                        if diff_percent <= -target_pct:
                            new_status = 'Predicted Target Hit'
                        elif diff_percent >= stop_pct:
                            new_status = 'Reacted Against Prediction'
                    
                    # TIME-BASED EXPIRY: If trade hasn't resolved in 3 days, expire it
                    if new_status == 'Active View':
                        try:
                            created_dt = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                            age_hours = (datetime.now(timezone.utc).replace(tzinfo=None) - created_dt).total_seconds() / 3600
                            if age_hours >= 72:  # 3 days
                                new_status = 'Expired'
                        except:
                            pass
                            
                    c.execute("UPDATE stock_impact SET current_price = ?, status = ? WHERE id = ?", (current_price, new_status, stock_id))
                    
                    # ENSEMBLE LEARNING LOOP: Save resolved signals to historical_patterns
                    if new_status in ['Predicted Target Hit', 'Reacted Against Prediction']:
                        c.execute("SELECT headline FROM news WHERE id = ?", (news_id,))
                        news_row = c.fetchone()
                        if news_row:
                            headline = news_row[0]
                            outcome = 'HIT' if new_status == 'Predicted Target Hit' else 'MISS'
                            direction = 'BULLISH' if is_bullish else 'BEARISH'
                            c.execute('''INSERT INTO historical_patterns (headline, ticker, direction, outcome, change_pct)
                                         VALUES (?, ?, ?, ?, ?)''', (headline, ticker, direction, outcome, diff_percent))
                                         
                except Exception as e:
                    pass
                
            conn.commit()
            conn.close()
        except Exception as e:
            print("YFinance Worker Error:", e)
            
        time.sleep(60)

# Threading starts moved to main block to prevent Flask reloader duplicate race conditions.

# ==========================================
# APP ROUTES
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/indices', methods=['GET'])
def get_indices():
    from datetime import timezone, timedelta as td
    ist = timezone(td(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    weekday = now_ist.weekday()  # 0=Mon … 4=Fri, 5=Sat, 6=Sun
    hour, minute = now_ist.hour, now_ist.minute

    market_open = (
        weekday < 5 and
        ((hour == 9 and minute >= 15) or (10 <= hour <= 14) or
         (hour == 15 and minute <= 30))
    )

    if market_open:
        price_label = "Live"
        market_status = "Market Open"
    else:
        price_label = "Prev. Close"
        if weekday >= 5:
            market_status = "Market Closed · Opens Mon 9:15 AM IST"
        elif hour < 9 or (hour == 9 and minute < 15):
            market_status = "Market Closed · Opens at 9:15 AM IST"
        else:
            market_status = "Market Closed · Closed at 3:30 PM IST"

    indices = [
        {"symbol": "^NSEI",    "name": "NIFTY 50"},
        {"symbol": "^BSESN",   "name": "SENSEX"},
        {"symbol": "^NSEBANK", "name": "BANK NIFTY"},
        {"symbol": "^NSMIDCP", "name": "MIDCAP NIFTY"},
    ]
    result = []
    for idx in indices:
        try:
            t = yf.Ticker(idx["symbol"])
            info = t.fast_info
            price = info.last_price
            prev_close = info.previous_close
            # When market is closed show 0% change — price shown is last recorded price
            if market_open and prev_close and prev_close > 0:
                change_pct = ((price - prev_close) / prev_close) * 100
            else:
                change_pct = 0.0
            result.append({
                "name": idx["name"],
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "is_live": market_open,
                "price_label": price_label,
                "market_status": market_status
            })
        except Exception as e:
            result.append({"name": idx["name"], "price": None, "change_pct": 0.0,
                           "is_live": market_open, "price_label": price_label,
                           "market_status": market_status})
    return jsonify(result)

@app.route('/api/news/top', methods=['GET'])
def get_top_news():
    try:
        conn = connect_news_db()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM news ORDER BY created_at DESC LIMIT 1")
        news_row = c.fetchone()
        
        if not news_row:
            conn.close()
            return jsonify([{
                "headline": "AI Engine is analyzing LiveMint, ET, and MoneyControl...",
                "news_time": "System Processing",
                "aam_janta_translation": "The background engine is downloading and filtering live market data. Please wait.",
                "macro_pathway": ["Scrape", "Filter", "Analyze", "Deploy"],
                "affected_stocks": []
            }])
        
        news_item = dict(news_row)
        try:
            news_item['macro_pathway'] = json.loads(news_item['macro_pathway'])
        except:
            news_item['macro_pathway'] = []
            
        c.execute("SELECT * FROM stock_impact WHERE news_id = ?", (news_item['id'],))
        stocks = [dict(s) for s in c.fetchall()]
        news_item['affected_stocks'] = stocks
        conn.close()
        return jsonify([news_item])
    except Exception as e:
        print("Error fetching top news", e)
        return jsonify([])

@app.route('/api/news/all', methods=['GET'])
def get_all_news():
    try:
        conn = connect_news_db()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Only return news from the last 4 days (by DB insertion time, not RSS publish date)
        four_days_ago = (datetime.now(timezone.utc) - timedelta(days=4)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("SELECT * FROM news WHERE created_at >= ? ORDER BY created_at DESC", (four_days_ago,))
        news_rows = c.fetchall()
        
        all_news = []
        for row in news_rows:
            news_item = dict(row)
            try:
                news_item['macro_pathway'] = json.loads(news_item['macro_pathway'])
            except:
                news_item['macro_pathway'] = []
            c.execute("SELECT * FROM stock_impact WHERE news_id = ?", (news_item['id'],))
            stocks = [dict(s) for s in c.fetchall()]
            news_item['affected_stocks'] = stocks
            all_news.append(news_item)
            
        conn.close()
        return jsonify(all_news)
    except Exception as e:
        print("Error fetching all news", e)
        return jsonify([])

@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    otp = str(random.randint(100000, 999999))
    OTP_STORE[email] = otp

    message = Mail(
        from_email='verified_sender@yourdomain.com',  # <--- CHANGE THIS TO YOUR VERIFIED SENDGRID EMAIL
        to_emails=email,
        subject='Alpha Lens - Your Authentication Code',
        html_content=f'''
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2>Welcome to Alpha Lens</h2>
                <p>Your secure, one-time login code is:</p>
                <h1 style="color: #06b6d4; font-size: 32px; letter-spacing: 5px;">{otp}</h1>
                <p>This code will expire in 10 minutes.</p>
            </div>
        '''
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        return jsonify({"message": "OTP sent successfully!"}), 200
    except Exception as e:
        print(f"SendGrid Error: {e}")
        return jsonify({"error": "Failed to send email via SendGrid. Check your Verified Sender Identity."}), 500

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email')
    user_otp = data.get('otp')

    if not email or email not in OTP_STORE or OTP_STORE[email] != user_otp:
        return jsonify({"error": "Invalid or expired OTP."}), 401

    del OTP_STORE[email]

    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT email FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        
        if not user:
            dummy_password = generate_password_hash(secrets.token_hex(16))
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, dummy_password))
            conn.commit()
        
        conn.close()
        session['user'] = email
        return jsonify({"message": "Authentication successful", "user": email}), 200
    except Exception as e:
        return jsonify({"error": "Database error occurred."}), 500

@app.route('/api/oauth-signin', methods=['POST'])
def oauth_signin():
    data = request.json
    account_id = data.get('account_id') 

    if not account_id:
        return jsonify({"error": "Account ID required"}), 400

    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT email FROM users WHERE email = ?", (account_id,))
        user = c.fetchone()
        
        if not user:
            dummy_password = generate_password_hash(secrets.token_hex(16))
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (account_id, dummy_password))
            conn.commit()
        
        conn.close()
        session['user'] = account_id
        return jsonify({"message": "Authentication successful", "user": account_id}), 200
    except Exception as e:
        return jsonify({"error": "Database error occurred."}), 500

@app.route('/api/me', methods=['GET'])
def get_current_user():
    if 'user' in session:
        return jsonify({"user": session['user']}), 200
    return jsonify({"user": None}), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"message": "Logged out"}), 200

if __name__ == '__main__':
    # Start background threads
    engine_thread = threading.Thread(target=ai_news_worker, daemon=True)
    engine_thread.start()

    yf_thread = threading.Thread(target=yfinance_worker, daemon=True)
    yf_thread.start()

    # Threaded=True allows the background AI loop to run alongside the website
    # use_reloader=False prevents double execution of our background threads on restart
    app.run(debug=True, port=5000, threaded=True, use_reloader=False)