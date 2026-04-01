from flask import Flask, render_template, jsonify
import requests
import google.generativeai as genai
import json
import yfinance as yf
from datetime import datetime

app = Flask(__name__, template_folder='.')

# --- CONFIGURATION ---
NEWS_API_KEY = "86e94c83a01c4953bc6b9cccb33f1154"
GEMINI_API_KEY = "AIzaSyABS1FGUxLRNcekIfquMcIKcGVjKd-bGq4"

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
            # Fallback if no breaking top-headlines exist currently
            fallback_url = f"https://newsapi.org/v2/everything?q=(India AND (business OR NSE OR BSE))&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
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
        
        # Add live baseline prices AT THE EXACT TIME OF NEWS
        current_time = datetime.now().strftime("%I:%M %p")
        for stock in analysis.get('affected_stocks', []):
            live_price, _ = get_live_price(stock['ticker'])
            stock['news_time'] = current_time
            stock['price_at_news'] = live_price
            stock['current_price'] = live_price
            
        system_state["latest_news"] = analysis
        return jsonify(analysis)
        
    except Exception as e:
        return jsonify({"error": str(e)})

# --- ROUTE 3: 10-SECOND LLM RE-EVALUATION LOOP ---
@app.route('/api/market_update')
def market_update():
    if not system_state["latest_news"]:
        return jsonify({"status": "waiting"})
        
    news = system_state["latest_news"]
    
    # 1. Update current prices
    for stock in news['affected_stocks']:
        live_price, _ = get_live_price(stock['ticker'])
        stock['current_price'] = live_price
        
    # 2. Ask Gemini to re-evaluate the view based on price movement
    # We bundle all stocks into ONE prompt to save your API rate limits!
    eval_prompt = f"""
    You are a quantitative trading system. Review these stocks. 
    If a stock was predicted 'bullish' and its Current Price is significantly higher than its Price At News (or vice versa for bearish), change its 'view' to 'Already Reacted'. Otherwise keep it as 'short-term now'.
    
    Data: {json.dumps(news['affected_stocks'])}
    
    Output STRICTLY as a JSON array of objects containing ONLY the ticker and the updated view:
    [{{ "ticker": "RELIANCE.NS", "view": "Already Reacted" }}]
    """
    
    try:
        ai_resp = model.generate_content(eval_prompt, generation_config={"response_mime_type": "application/json"})
        updated_views = json.loads(ai_resp.text)
        
        # Merge updated views back into our global state
        for updated_stock in updated_views:
            for active_stock in news['affected_stocks']:
                if active_stock['ticker'] == updated_stock['ticker']:
                    active_stock['view'] = updated_stock['view']
                    
    except Exception as e:
        print("Re-eval Error:", e)

    return jsonify(news)

if __name__ == '__main__':
    print("🚀 Starting IN-SIGHT LIVE QUANT SERVER on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)