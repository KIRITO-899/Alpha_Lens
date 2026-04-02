import google.generativeai as genai
import json
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import time
import csv
import os

# --- API KEY ROTATOR SETUP ---
API_KEYS = [
    "AIzaSyDkS2vjNmGCQXwqUjhYx5dMdP_qwwQlqTU",
    "AIzaSyCwfJoSmYAq_qug6MNFAGGEwEbsUVIKnkU",
    "AIzaSyCxkI_gygGGhcZwKgaQOqOi0C1d3YQPMCY"
]
current_key_idx = 0

genai.configure(api_key=API_KEYS[current_key_idx])
model = genai.GenerativeModel('gemini-2.5-flash')

# Trade Logic Thresholds (1% Target, 1% Stop Loss)
TARGET_PCT = 1.0    
STOP_PCT = -2.0     

def clean_json(raw_text):
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"): 
        cleaned = cleaned[7:]
    if cleaned.startswith("```"): 
        cleaned = cleaned[3:]
    if cleaned.endswith("```"): 
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())

def get_evaluation_prices(ticker, news_time_str):
    """
    Fetches the Base Price, Day 1 Price (T+24h), and Day 2 Price (T+48h)
    elegantly skipping weekends and holidays.
    """
    try:
        if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
            ticker += '.NS'
            
        ist = pytz.timezone('Asia/Kolkata')
        base_time = ist.localize(datetime.strptime(news_time_str, "%Y-%m-%d %H:%M"))
        
        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d", interval="15m")
        
        if hist.empty:
            return None, None, None

        hist.index = hist.index.tz_convert('Asia/Kolkata')
        
        # Base Price
        base_data = hist[hist.index >= base_time]
        if base_data.empty:
            return None, None, None
        base_price = round(base_data['Close'].iloc[0], 2)
        actual_base_time = base_data.index[0]
        
        # Day 1 Price (At least 24 hours later)
        day1_target_time = actual_base_time + timedelta(hours=24)
        day1_data = hist[hist.index >= day1_target_time]
        
        if day1_data.empty:
            return base_price, None, None
            
        day1_price = round(day1_data['Close'].iloc[0], 2)
        actual_day1_time = day1_data.index[0]
        
        # Day 2 Price (At least 24 hours after Day 1)
        day2_target_time = actual_day1_time + timedelta(hours=24)
        day2_data = hist[hist.index >= day2_target_time]
        
        if day2_data.empty:
            day2_price = None # Hasn't happened yet
        else:
            day2_price = round(day2_data['Close'].iloc[0], 2)
            
        return base_price, day1_price, day2_price

    except Exception as e:
        return None, None, None

def evaluate_trade(ai_impact, pct_change):
    ai_impact = ai_impact.lower()
    
    if 'bull' in ai_impact:
        if pct_change >= TARGET_PCT: return "TARGET_HIT"
        elif pct_change <= STOP_PCT: return "STOP_HIT"
        else: return "STILL_RUNNING"
            
    elif 'bear' in ai_impact:
        if pct_change <= -TARGET_PCT: return "TARGET_HIT"
        elif pct_change >= -STOP_PCT: return "STOP_HIT"
        else: return "STILL_RUNNING"
            
    return "NEUTRAL"

def run_bulk_backtest(csv_filename):
    global current_key_idx, model
    
    print("\n==================================================")
    print(" 🚀 ELITE TIER-1 BULK QUANT BACKTESTER")
    print("==================================================")
    
    if not os.path.exists(csv_filename):
        print(f"ERROR: Could not find '{csv_filename}'.")
        return

    stats = {
        "total_news_processed": 0,
        "total_predictions_made": 0,
        "target_hit": 0,
        "stop_hit": 0,
        "still_running": 0,
        "api_errors": 0,
        "data_errors": 0
    }

    with open(csv_filename, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        
        print(f"Found {len(rows)} articles to process.")
        print("Note: Multi-Key Rotation Engine Active. High-Conviction filtering ON.\n")
        
        for index, row in enumerate(rows):
            news_time = row['Datetime'].strip()
            news_text = row['Headline'].strip()
            
            stats["total_news_processed"] += 1
            print(f"[{index+1}/{len(rows)}] Analyzing: {news_text[:50]}...")

            prompt = f"""
            You are a Tier-1 Quantitative Portfolio Manager. Analyze this historical news from exactly {news_time}: 
            '{news_text}'
            
            HIGH-CONVICTION EDGE RULES:
            1. If the news is ambiguous, already priced in, or has low direct impact, DO NOT FORCE A TRADE. Return an empty array: [].
            2. Only pick 1 or 2 specific Indian stocks (tickers ending in .NS) if they have a MASSIVE, undeniable directional bias based on this news.
            3. Think 2nd order: E.g., Crude oil prices crash -> Short ONGC (Bearish), Buy Asian Paints (Bullish).
            
            Output STRICTLY as JSON:
            {{
              "affected_stocks": [
                {{
                    "ticker": "TICKER.NS",
                    "predicted_impact": "bullish" | "bearish"
                }}
              ]
            }}
            """

            # --- API ROTATION & RETRY LOGIC ---
            success = False
            retries = 0
            stocks = []
            
            while not success and retries < 3:
                try:
                    ai_resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                    analysis = clean_json(ai_resp.text)
                    stocks = analysis.get('affected_stocks', [])
                    success = True
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in error_msg or "403" in error_msg or "quota" in error_msg or "key" in error_msg:
                        # Rotate Key
                        current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                        print(f"    -> Key limit reached. Swapping to API Key {current_key_idx + 1}...")
                        genai.configure(api_key=API_KEYS[current_key_idx])
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        time.sleep(2)
                        retries += 1
                    else:
                        print(f"    -> ❌ AI Parsing Error: {e}")
                        break

            if not success:
                stats["api_errors"] += 1
                continue
                
            if not stocks:
                print("    -> 🛑 AI passed on this trade (Low Conviction setup).")
                time.sleep(4.5)
                continue
                
            # --- EVALUATION LOGIC ---
            for stock in stocks:
                ticker = stock['ticker']
                impact = stock['predicted_impact']
                
                stats["total_predictions_made"] += 1
                
                base_p, d1_p, d2_p = get_evaluation_prices(ticker, news_time)
                
                if base_p is None or d1_p is None:
                    stats["data_errors"] += 1
                    print(f"    -> {ticker}: Market Data Missing (Too old or bad ticker)")
                    continue
                    
                # Check Day 1
                pct1 = round(((d1_p - base_p) / base_p) * 100, 2)
                res1 = evaluate_trade(impact, pct1)
                
                if res1 != "STILL_RUNNING":
                    # Trade resolved on Day 1
                    if res1 == "TARGET_HIT": stats["target_hit"] += 1
                    elif res1 == "STOP_HIT": stats["stop_hit"] += 1
                    print(f"    -> {ticker} ({impact.upper()}): {res1} on Day 1 ({pct1}%)")
                else:
                    # Trade is still running, check Day 2
                    if d2_p is not None:
                        pct2 = round(((d2_p - base_p) / base_p) * 100, 2)
                        res2 = evaluate_trade(impact, pct2)
                        
                        if res2 == "TARGET_HIT": stats["target_hit"] += 1
                        elif res2 == "STOP_HIT": stats["stop_hit"] += 1
                        elif res2 == "STILL_RUNNING": stats["still_running"] += 1
                        
                        print(f"    -> {ticker} ({impact.upper()}): {res2} on Day 2 Check ({pct2}%)")
                    else:
                        # Day 2 hasn't happened yet in real life
                        stats["still_running"] += 1
                        print(f"    -> {ticker} ({impact.upper()}): STILL_RUNNING (Day 2 pending market open)")

            # Throttling to protect the active key
            time.sleep(4.5)

    # --- FINAL REPORT GENERATION ---
    print("\n==================================================")
    print(" 📊 FINAL HIGH-CONVICTION STATISTICS REPORT")
    print("==================================================")
    print(f"Total News Articles Processed:  {stats['total_news_processed']}")
    print(f"Total Predictions Triggered:    {stats['total_predictions_made']}")
    print("-" * 50)
    
    completed_trades = stats['target_hit'] + stats['stop_hit']
    win_rate = 0
    if completed_trades > 0:
        win_rate = round((stats['target_hit'] / completed_trades) * 100, 2)

    print(f"✅ TARGET HIT (Wins):             {stats['target_hit']}")
    print(f"❌ STOP HIT (Losses):             {stats['stop_hit']}")
    print(f"⏳ STILL RUNNING (Consolidating): {stats['still_running']}")
    print("-" * 50)
    print(f"🏆 AI STRATEGY WIN RATE:          {win_rate}%")
    print("-" * 50)
    print(f"Data Fetch Errors:             {stats['data_errors']}")
    print(f"API Limit Blocks Dodged:       {stats['api_errors']}")
    print("==================================================\n")

if __name__ == "__main__":
    run_bulk_backtest("news_dataset.csv")