from flask import Flask, render_template, jsonify
import requests
import google.generativeai as genai
import json
<<<<<<< HEAD
import yfinance as yf
from datetime import datetime, timedelta

app = Flask(__name__)

# --- API CONFIGURATION ---
NEWS_API_KEY = "86e94c83a01c4953bc6b9cccb33f1154"
GEMINI_API_KEY = "AIzaSyDyaZeVjVwK5h3luZUrhBIPaKZmaoKpRfc" 

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# GLOBAL STATE: Temporary database to track prices over time
system_state = {
    "latest_news": None
}

# --- HELPER: GET LIVE PRICE FAST & SAFELY ---
def get_live_price(ticker):
    """Uses yfinance history to get live/closed market data safely."""
    try:
        if not ticker.endswith('.NS') and not ticker.endswith('.BO') and not ticker.startswith('^'):
            ticker += '.NS'
            
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2d")
        if hist.empty:
            return 0.0, 0.0
            
        current_price = round(hist['Close'].iloc[-1], 2)
        prev_close = round(hist['Close'].iloc[-2] if len(hist) > 1 else current_price, 2)
        
        pct_change = 0.0
        if prev_close > 0:
            pct_change = round(((current_price - prev_close) / prev_close) * 100, 2)
            
        return current_price, pct_change
    except Exception as e:
        print(f"YFinance Error for {ticker}: {e}")
        return 0.0, 0.0

# --- HELPER: CLEAN AI JSON ---
def clean_json_response(raw_text):
    """Strips markdown formatting that crashes the JSON parser"""
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())

@app.route('/')
def home():
    # Flask automatically looks inside the "templates" folder for this file
    return render_template('index.html')

# --- ROUTE 1: FETCH THE LIVE SCROLLING TICKER ---
@app.route('/api/indices')
def get_indices():
    indices = {
        "NIFTY 50": "^NSEI", 
        "SENSEX": "^BSESN", 
        "BANK NIFTY": "^NSEBANK",
        "MIDCAP NIFTY": "^NSEMDCP50"
    }
    data = []
    for name, symbol in indices.items():
        price, change = get_live_price(symbol)
        data.append({"name": name, "price": price, "change": change})
    return jsonify(data)

# --- ROUTE 2: INITIAL AI NEWS FETCH (ELITE QUANT UPGRADE) ---
@app.route('/api/news')
def get_news():
    headers = {"User-Agent": "Mozilla/5.0"}
    primary_url = f"[https://newsapi.org/v2/top-headlines?country=in&category=business&apiKey=](https://newsapi.org/v2/top-headlines?country=in&category=business&apiKey=){NEWS_API_KEY}"
    fallback_url = f"[https://newsapi.org/v2/everything?q=(India](https://newsapi.org/v2/everything?q=(India) AND (business OR NSE OR BSE))&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    try:
        # Attempt 1: Live Top Headlines
        response = requests.get(primary_url, headers=headers)
        articles = response.json().get('articles', [])
        
        # Attempt 2: Fallback if empty
        if not articles:
            response = requests.get(fallback_url, headers=headers)
            articles = response.json().get('articles', [])
            
        if not articles:
             return jsonify({"error": "No news found currently."})
             
        article = articles[0] 
        news_text = f"{article.get('title')}. {article.get('description', '')}"
        
        # EXACT TIME EXTRACTION (Converting UTC to IST)
        raw_utc_time = article.get('publishedAt', '') 
        try:
            utc_dt = datetime.strptime(raw_utc_time, "%Y-%m-%dT%H:%M:%SZ")
            ist_dt = utc_dt + timedelta(hours=5, minutes=30)
            exact_news_time = ist_dt.strftime("%I:%M %p")
        except:
            exact_news_time = datetime.now().strftime("%I:%M %p")
        
        # ELITE QUANT PROMPT
        prompt = f"""
        You are an elite quantitative analyst and portfolio manager for a top-tier hedge fund specializing in the Indian equity market (NSE/BSE). Your edge is contrarian thinking, understanding market microstructure, and knowing when news is "already priced in" by institutional algorithms.
        
        Analyze this Indian market news: '{news_text}'
        
        Do NOT make amateur linear assumptions. Consider if the market expected this, how the broader sector is trending, and the historical reaction of these specific stocks.

        Output STRICTLY as JSON without markdown formatting:
        {{
          "headline": "Short punchy summary",
          "market_context": "Brief analysis of the broader macroeconomic or sector condition regarding this news.",
          "affected_stocks": [
            {{
                "ticker": "TICKER.NS",
                "impact": "bullish" | "slightly bullish" | "bearish" | "slightly bearish" | "neutral",
                "view": "short-term now" | "long-term" | "already priced in" | "mean reversion expected",
                "quantitative_reasoning": "Deep explanation considering factors like institutional holding, historical reaction, or whether the street expected worse/better.",
                "risk_overturn": "What specific upcoming data point or event would invalidate this thesis?"
            }}
          ]
        }}
        """
        
        ai_resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        analysis = clean_json_response(ai_resp.text)
        
        # Add live baseline prices AT THE EXACT TIME OF NEWS
        for stock in analysis.get('affected_stocks', []):
            live_price, _ = get_live_price(stock['ticker'])
            stock['news_time'] = exact_news_time
            stock['price_at_news'] = live_price
            stock['current_price'] = live_price
            
        system_state["latest_news"] = analysis
        return jsonify(analysis)
        
    except Exception as e:
        print("Backend Fetch Error:", e)
        return jsonify({"error": str(e)})

# --- ROUTE 3: 10-SECOND MATH RE-EVALUATION LOOP ---
@app.route('/api/market_update')
def market_update():
    if not system_state["latest_news"]:
        return jsonify({"status": "waiting"})
        
    news = system_state["latest_news"]
    
    # Update prices purely via math to avoid rate limits on the LLM
    for stock in news.get('affected_stocks', []):
        live_price, _ = get_live_price(stock['ticker'])
        if live_price > 0:
            stock['current_price'] = live_price
            
            # Algorithmic Check: Has the market reacted?
            # If price moved by > 0.2% in the predicted direction, flip to 'Already Reacted'
            if stock['price_at_news'] > 0:
                percent_change = ((live_price - stock['price_at_news']) / stock['price_at_news']) * 100
                impact = stock.get('impact', '').lower()
                
                if 'bull' in impact and percent_change >= 0.2:
                    stock['view'] = "Already Reacted"
                elif 'bear' in impact and percent_change <= -0.2:
                    stock['view'] = "Already Reacted"

    return jsonify(news)

if __name__ == '__main__':
    print("🚀 Starting IN-SIGHT LIVE QUANT SERVER on [http://127.0.0.1:5000](http://127.0.0.1:5000)")
    app.run(debug=True, port=5000)
=======

app = Flask(__name__, template_folder='.')

# --- API CONFIGURATION ---
NEWS_API_KEY = "86e94c83a01c4953bc6b9cccb33f1154"
GEMINI_API_KEY = "AIzaSyABS1FGUxLRNcekIfquMcIKcGVjKd-bGq4"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def fetch_and_analyze():
    # 1. Fetch Live Indian News (With dynamic fallback to ensure data)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    primary_url = f"https://newsapi.org/v2/top-headlines?country=in&category=business&apiKey={NEWS_API_KEY}"
    fallback_url = f"https://newsapi.org/v2/everything?q=(India AND (business OR NSE OR BSE))&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(primary_url, headers=headers)
        articles = response.json().get('articles', [])
        
        if not articles or response.status_code != 200:
            print("Fallback triggered: Fetching latest India business news...")
            response = requests.get(fallback_url, headers=headers)
            articles = response.json().get('articles', [])

        if not articles:
            return [{"error": "No news found currently."}]
            
        results = []
        for article in articles[:3]: # Process top 3 news items
            news_text = f"{article.get('title')}. {article.get('description', '')}"
            
            # 2. Force the AI to output exact JSON for our UI
            prompt = f"""
            Analyze this Indian market news: '{news_text}'
            Output STRICTLY as JSON:
            {{
              "headline": "Short punchy summary of the event",
              "aam_janta_translation": "1 sentence explaining everyday life impact",
              "macro_pathway": ["Trigger", "Immediate Hit", "Ripple", "Macro Result"],
              "affected_stocks": [
                {{
                    "ticker": "TICKER.NS",
                    "impact": "bullish" | "slightly bullish" | "bearish" | "slightly bearish",
                    "view": "short-term now" | "long-term" | "already reacted",
                    "estimated_change_percent": 1.5,
                    "reason": "Brief reason why"
                }}
              ]
            }}
            """
            try:
                ai_resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                analysis = json.loads(ai_resp.text)
                results.append(analysis)
            except Exception as e:
                print("AI Parse Error:", e)
                
        if not results:
            return [{"error": "AI error or rate limit exceeded. Please wait a minute and reload."}]
            
        return results
    except Exception as e:
        return [{"error": str(e)}]

# Serve the HTML frontend
@app.route('/')
def home():
    return render_template('index.html')

# API endpoint for the frontend JavaScript to call
@app.route('/api/news')
def get_news():
    data = fetch_and_analyze()
    return jsonify(data)

if __name__ == '__main__':
    print("🚀 Starting IN-SIGHT Local Server on http://127.0.0.1:5000")
    app.run(debug=True)
>>>>>>> dd316150137a9d496e3a74b615e216d13f13f4bd
