from flask import Flask, render_template, jsonify
import requests
import google.generativeai as genai
import json
import yfinance as yf
from datetime import datetime, timedelta
import os

app = Flask(__name__, template_folder='.')

# --- CONFIGURATION ---
NEWS_API_KEY = "86e94c83a01c4953bc6b9cccb33f1154"
GEMINI_API_KEY = "AIzaSyBlvMiHYl3dCIboqzLz-i3LnrSmwzLHxEc"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# GLOBAL STATE: This acts as our temporary database to track prices over time
system_state = {
    "latest_news": None
}

# --- HELPER: GET LIVE PRICE FAST ---
def get_live_price(ticker):
    """Uses yfinance fast_info to get live/closed market data in milliseconds"""
    try:
        # Append .NS for National Stock Exchange if missing
        if not ticker.endswith('.NS') and not ticker.endswith('.BO') and not ticker.startswith('^'):
            ticker += '.NS'
            
        info = yf.Ticker(ticker).fast_info
        current_price = round(info.last_price, 2)
        prev_close = round(info.previous_close, 2)
        pct_change = round(((current_price - prev_close) / prev_close) * 100, 2)
        return current_price, pct_change
    except:
        return 0.0, 0.0

def save_daily_log(news_data):
    """Saves the news and its live stock tracing to a local file for output verification."""
    log_file = "verification_log.json"
    logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                logs = json.load(f)
        except:
            pass
            
    # Check if this headline is already logged, update its live prices
    headline_exists = False
    for log in logs:
        if log.get("headline") == news_data.get("headline"):
            log["affected_stocks"] = news_data.get("affected_stocks", [])
            log["last_updated"] = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            headline_exists = True
            break
            
    if not headline_exists:
        news_data["logged_at"] = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        logs.append(news_data)
        
    # Prune logs older than 1 day
    recent_logs = []
    for log in logs:
        try:
            log_time_str = log.get("logged_at") or log.get("last_updated")
            log_time = datetime.strptime(log_time_str, "%Y-%m-%d %I:%M:%S %p")
            if datetime.now() - log_time <= timedelta(days=1):
                recent_logs.append(log)
        except:
            recent_logs.append(log) # keep if parse fails
            
    with open(log_file, "w") as f:
        json.dump(recent_logs, f, indent=4)

@app.route('/')
def home():
    return render_template('index-2.html')

# --- ROUTE 1: FETCH THE LIVE SCROLLING TICKER ---
@app.route('/api/indices')
def get_indices():
    indices = {
        "NIFTY 50": "^NSEI",
        "SENSEX": "^BSESN",
        "BANK NIFTY": "^NSEBANK"
    }
    data = []
    for name, symbol in indices.items():
        price, change = get_live_price(symbol)
        data.append({"name": name, "price": price, "change": change})
    return jsonify(data)

# --- ROUTE 2: FETCH NEWS & SET BASELINE PRICE ---
@app.route('/api/news')
def get_news():
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://newsapi.org/v2/top-headlines?country=in&category=business&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url, headers=headers)
        articles = response.json().get('articles', [])
        
        if not articles:
            # Fallback to high-quality Indian financial domains to avoid random forum posts
            reputable_domains = "moneycontrol.com,economictimes.indiatimes.com,livemint.com,cnbctv18.com,ndtv.com"
            fallback_url = f"https://newsapi.org/v2/everything?q=(India AND (business OR NSE OR BSE))&domains={reputable_domains}&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
            response = requests.get(fallback_url, headers=headers)
            articles = response.json().get('articles', [])
            
        if not articles:
             return jsonify({"error": "No news found."})
             
        article = articles[0] # Grab just the absolute latest breaking news for focus
        news_text = f"{article.get('title')}. {article.get('description', '')}"
        
        prompt = f"""
        Analyze this Indian market news: '{news_text}'
        Output STRICTLY as JSON:
        {{
          "headline": "Short punchy summary",
          "aam_janta_translation": "1 sentence everyday impact",
          "affected_stocks": [
            {{
                "ticker": "RELIANCE.NS",
                "impact": "bullish",
                "view": "short-term now",
                "estimated_change_percent": 2.0,
                "reason": "Why it moves"
            }}
          ]
        }}
        """
        
        ai_resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        analysis = json.loads(ai_resp.text)
        
        # Add the news original publish time
        analysis["published_at"] = article.get("publishedAt", "Unknown Time")
        
        # Add live baseline prices AT THE EXACT TIME OF NEWS
        current_time = datetime.now().strftime("%I:%M %p")
        for stock in analysis.get('affected_stocks', []):
            live_price, _ = get_live_price(stock['ticker'])
            stock['news_time'] = current_time
            stock['price_at_news'] = live_price
            stock['current_price'] = live_price
            
            
        save_daily_log(analysis)
        
        # Read the updated DB to pass to frontend as array
        log_file = "verification_log.json"
        with open(log_file, "r") as f:
            all_logs = json.load(f)
            
        return jsonify(all_logs[::-1])
        
    except Exception as e:
        return jsonify({"error": str(e)})

# --- ROUTE 3: 10-SECOND LLM RE-EVALUATION LOOP ---
@app.route('/api/market_update')
def market_update():
    log_file = "verification_log.json"
    if not os.path.exists(log_file):
        return jsonify({"status": "waiting"})
        
    try:
        with open(log_file, "r") as f:
            logs = json.load(f)
    except:
        return jsonify({"status": "waiting"})
        
    if not logs:
        return jsonify({"status": "waiting"})
        
    # 1. Update current prices for ALL stored logs to track live progression history
    for news_item in logs:
        for stock in news_item.get('affected_stocks', []):
            live_price, _ = get_live_price(stock['ticker'])
            stock['current_price'] = live_price
            
    # 2. Only re-evaluate the most recent arrival to save your Gemini Quota Limits!
    latest_news = logs[-1]
    
    eval_prompt = f"""
    You are a quantitative trading system. Review these stocks. 
    If a stock was predicted 'bullish' and its Current Price is significantly higher than its Price At News (or vice versa for bearish), change its 'view' to 'Already Reacted'. Otherwise keep it as 'short-term now'.
    
    Data: {json.dumps(latest_news['affected_stocks'])}
    
    Output STRICTLY as a JSON array of objects containing ONLY the ticker and the updated view:
    [{{ "ticker": "RELIANCE.NS", "view": "Already Reacted" }}]
    """
    
    try:
        ai_resp = model.generate_content(eval_prompt, generation_config={"response_mime_type": "application/json"})
        updated_views = json.loads(ai_resp.text)
        
        for updated_stock in updated_views:
            for active_stock in latest_news['affected_stocks']:
                if active_stock['ticker'] == updated_stock['ticker']:
                    active_stock['view'] = updated_stock['view']
    except Exception as e:
        print("Re-eval Error:", e)

    # Dump mutated logs back to file so past prices are persisted securely
    with open(log_file, "w") as f:
        json.dump(logs, f, indent=4)

    return jsonify(logs[::-1])

if __name__ == '__main__':
    print("🚀 Starting IN-SIGHT LIVE QUANT SERVER on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)