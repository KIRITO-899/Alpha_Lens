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

# ==========================================
# 2:1 REWARD-TO-RISK THRESHOLDS
# Target = 2× the Stop Loss → mathematically
# you only need >33% accuracy to break even,
# but with good signals you easily clear 60%.
# ==========================================
TARGET_PCT  = 2.0   # Profit target
STOP_PCT    = 1.0   # Stop-loss (half of target = 2:1 R:R)
MIN_CONFIDENCE = 75 # Only act on high-confidence signals

def clean_json(raw_text):
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def get_technical_confirmation(ticker, impact, news_time_str):
    """
    Verifies price momentum BEFORE the news event supports the signal direction.
    - Prevents fighting a strong contrary trend.
    """
    try:
        ist = pytz.timezone('Asia/Kolkata')
        base_time = ist.localize(datetime.strptime(news_time_str, "%Y-%m-%d %H:%M"))

        stock = yf.Ticker(ticker)
        # Get 30 days before the news event for momentum context
        hist_start = (base_time - timedelta(days=35)).strftime('%Y-%m-%d')
        hist_end   = (base_time + timedelta(days=1)).strftime('%Y-%m-%d')
        hist = stock.history(start=hist_start, end=hist_end, interval="1d")

        if hist.empty or len(hist) < 10:
            return True  # Allow through if data unavailable

        close = hist['Close']

        # RSI-14
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14).mean().iloc[-1]
        avg_loss = loss.rolling(14).mean().iloc[-1]
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        # 5-day vs 20-day SMA for short-term trend
        sma5  = close.rolling(5).mean().iloc[-1]
        sma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else sma5
        uptrend   = sma5 > sma20
        downtrend = sma5 < sma20

        impact_lower = impact.lower()
        is_bullish = 'bullish' in impact_lower

        # Block signal if technically overextended AGAINST the signal direction
        if is_bullish and rsi > 72 and downtrend:
            return False
        if not is_bullish and rsi < 28 and uptrend:
            return False

        return True

    except Exception:
        return True  # Never block a signal due to a data error


def get_evaluation_prices(ticker, news_time_str):
    """
    Fetches Base Price (at news time), Day 1 (~24h later), Day 2 (~48h later)
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

        # Day 1 (24h later)
        day1_target_time = actual_base_time + timedelta(hours=24)
        day1_data = hist[hist.index >= day1_target_time]
        if day1_data.empty:
            return base_price, None, None
        day1_price = round(day1_data['Close'].iloc[0], 2)
        actual_day1_time = day1_data.index[0]

        # Day 2 (48h later)
        day2_target_time = actual_day1_time + timedelta(hours=24)
        day2_data = hist[hist.index >= day2_target_time]
        day2_price = round(day2_data['Close'].iloc[0], 2) if not day2_data.empty else None

        return base_price, day1_price, day2_price

    except Exception:
        return None, None, None


def evaluate_trade(ai_impact, pct_change):
    """2:1 R:R evaluation: TARGET_PCT profit or STOP_PCT loss."""
    ai_impact = ai_impact.lower()

    if 'bull' in ai_impact:
        if pct_change >= TARGET_PCT:  return "TARGET_HIT"
        elif pct_change <= -STOP_PCT: return "STOP_HIT"
        else:                          return "STILL_RUNNING"

    elif 'bear' in ai_impact:
        if pct_change <= -TARGET_PCT: return "TARGET_HIT"
        elif pct_change >= STOP_PCT:  return "STOP_HIT"
        else:                          return "STILL_RUNNING"

    return "NEUTRAL"


def run_bulk_backtest(csv_filename):
    global current_key_idx, model

    print("\n==================================================")
    print(" ALPHA LENS HIGH-CONVICTION BACKTESTER v2")
    print(f"    Thresholds: Target={TARGET_PCT}% | Stop={STOP_PCT}% | Min Confidence={MIN_CONFIDENCE}")
    print("==================================================")

    if not os.path.exists(csv_filename):
        print(f"ERROR: Could not find '{csv_filename}'.")
        return

    stats = {
        "total_news_processed": 0,
        "total_predictions_made": 0,
        "skipped_low_confidence": 0,
        "skipped_tech_rejection": 0,
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
        print("Filters: Confidence Gate ON | Technical Confirmation ON | 2:1 R:R ON\n")

        for index, row in enumerate(rows):
            news_time = row['Datetime'].strip()
            news_text = row['Headline'].strip()
            stats["total_news_processed"] += 1
            print(f"[{index+1}/{len(rows)}] Analyzing: {news_text[:55]}...")

            # ── INSTITUTIONAL-GRADE AI PROMPT ───────────────────────────────
            prompt = f"""You are a senior quant analyst at a Tier-1 hedge fund managing Indian equities.
Your ONLY job is HIGH-CONVICTION, DIRECTIONAL calls. Getting it wrong costs real capital.

Historical news from {news_time}: '{news_text}'

STEP 1 - BRUTAL FILTER: Ask yourself:
- Is this already priced in? Is the direction genuinely unambiguous?
- Would a professional fund manager trade on this with conviction?

STEP 2 - SECOND-ORDER THINKING:
- Crude oil up → ONGC (Bullish), Airlines/Asian Paints (Bearish)
- FDA approval → Pharma stock (Bullish), generic competition (Bearish)
- Large order win → direct company (Bullish); Competitor concern (Slightly Bearish)
- Q3 miss → stock (Bearish), sector (Slightly Bearish sentiment)
- Rate cut → Banks/Realty/NBFCs (Bullish)

RULES — FOLLOW EXACTLY:
1. If ambiguous, macro-only without single clear stock, or already priced in → "ignore": true, empty array.
2. ONLY identify 1-2 NSE tickers (.NS) with absolutely clear directional bias.
3. "confidence_score" (integer 0–100): Be HONEST. Below 75 = low conviction = your system will skip it.
4. "predicted_impact": "bullish" or "bearish" ONLY.

Output STRICT JSON:
{{
  "ignore": false,
  "affected_stocks": [
    {{
        "ticker": "TICKER.NS",
        "predicted_impact": "bullish",
        "confidence_score": 88,
        "reason": "Concise second-order reasoning. Max 1 sentence."
    }}
  ]
}}
"""

            success = False
            retries = 0
            stocks = []

            while not success and retries < 3:
                try:
                    ai_resp = model.generate_content(
                        prompt, generation_config={"response_mime_type": "application/json"}
                    )
                    analysis = clean_json(ai_resp.text)
                    if analysis.get("ignore", False):
                        stocks = []
                    else:
                        stocks = analysis.get('affected_stocks', [])
                    success = True
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in error_msg or "403" in error_msg or "quota" in error_msg or "key" in error_msg:
                        current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                        print(f"    -> Key limit. Swapping to API Key {current_key_idx + 1}...")
                        genai.configure(api_key=API_KEYS[current_key_idx])
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        time.sleep(2)
                        retries += 1
                    else:
                        print(f"    -> [X] AI Error: {e}")
                        break

            if not success:
                stats["api_errors"] += 1
                continue

            if not stocks:
                print("    -> [STOP] AI passed (Low conviction / ambiguous news).")
                time.sleep(4.5)
                continue

            # ── EVALUATION LOOP ──────────────────────────────────────────────
            for stock in stocks:
                ticker   = stock['ticker']
                impact   = stock['predicted_impact']
                conf     = stock.get('confidence_score', 80)

                # ── GATE 1: Confidence Score Filter ─────────────────────────
                if conf < MIN_CONFIDENCE:
                    stats["skipped_low_confidence"] += 1
                    print(f"    -> [!]  {ticker}: Skipped (confidence {conf} < {MIN_CONFIDENCE})")
                    continue

                # ── GATE 2: Technical Confirmation ───────────────────────────
                tech_ok = get_technical_confirmation(ticker, impact, news_time)
                if not tech_ok:
                    stats["skipped_tech_rejection"] += 1
                    print(f"    -> [TECH] {ticker}: Skipped (technicals contradict {impact} signal)")
                    continue

                stats["total_predictions_made"] += 1

                base_p, d1_p, d2_p = get_evaluation_prices(ticker, news_time)

                if base_p is None or d1_p is None:
                    stats["data_errors"] += 1
                    print(f"    -> {ticker}: Market data missing.")
                    continue

                # Check Day 1
                pct1 = round(((d1_p - base_p) / base_p) * 100, 2)
                res1 = evaluate_trade(impact, pct1)

                if res1 != "STILL_RUNNING":
                    if res1 == "TARGET_HIT":   stats["target_hit"] += 1
                    elif res1 == "STOP_HIT":   stats["stop_hit"] += 1
                    print(f"    -> {ticker} ({impact.upper()}, conf={conf}): {res1} on Day 1 ({pct1:+.2f}%)")
                else:
                    if d2_p is not None:
                        pct2 = round(((d2_p - base_p) / base_p) * 100, 2)
                        res2 = evaluate_trade(impact, pct2)
                        if res2 == "TARGET_HIT":     stats["target_hit"] += 1
                        elif res2 == "STOP_HIT":     stats["stop_hit"] += 1
                        elif res2 == "STILL_RUNNING": stats["still_running"] += 1
                        print(f"    -> {ticker} ({impact.upper()}, conf={conf}): {res2} on Day 2 ({pct2:+.2f}%)")
                    else:
                        stats["still_running"] += 1
                        print(f"    -> {ticker} ({impact.upper()}): STILL_RUNNING (Day 2 pending)")

            time.sleep(4.5)

    # ── FINAL STATISTICS REPORT ──────────────────────────────────────────────
    print("\n==================================================")
    print(" HIGH-CONVICTION BACKTEST RESULTS")
    print("==================================================")
    print(f"News Articles Processed:    {stats['total_news_processed']}")
    print(f"Predictions Triggered:      {stats['total_predictions_made']}")
    print(f"Skipped (Low Confidence):   {stats['skipped_low_confidence']}")
    print(f"Skipped (Tech Rejection):   {stats['skipped_tech_rejection']}")
    print("-" * 50)

    completed = stats['target_hit'] + stats['stop_hit']
    win_rate = 0
    if completed > 0:
        win_rate = round((stats['target_hit'] / completed) * 100, 2)

    print(f" TARGET HIT (Wins):        {stats['target_hit']}")
    print(f" STOP HIT (Losses):        {stats['stop_hit']}")
    print(f" STILL RUNNING:            {stats['still_running']}")
    print("-" * 50)

    if win_rate >= 60:
        rating = " TARGET ACHIEVED (60%+)"
    elif win_rate >= 50:
        rating = " MODERATE — needs more filtering"
    else:
        rating = " BELOW TARGET — increase MIN_CONFIDENCE"

    print(f" WIN RATE:                 {win_rate}%  <- {rating}")
    print("-" * 50)
    print(f"Data Errors:               {stats['data_errors']}")
    print(f"API Errors Dodged:         {stats['api_errors']}")
    print("==================================================\n")

    with open("backtest_results.txt", "w", encoding="utf-8") as f:
        f.write(f"Total News: {stats['total_news_processed']}\n")
        f.write(f"Predictions: {stats['total_predictions_made']}\n")
        f.write(f"Wins: {stats['target_hit']}\n")
        f.write(f"Losses: {stats['stop_hit']}\n")
        f.write(f"Win Rate: {win_rate}%\n")

    return win_rate


if __name__ == "__main__":
    run_bulk_backtest("news_dataset.csv")