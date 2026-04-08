import pandas as pd
from datetime import datetime
import json
import logging
logger = logging.getLogger('yfinance')
logger.disabled = True
import backtest

def quick_analyze():
    print("Loading news_dataset.csv...")
    try:
        df = pd.read_csv("news_dataset.csv").head(15)
    except Exception as e:
        print("Failed to load CSV:", e)
        return

    for idx, row in df.iterrows():
        headline = row['Headline']
        news_time = row['Datetime']
        
        # We don't want to use API quota unless necessary. We can try to just use API for the first 3.
        # But wait, quota reset, so let's just use it cautiously.
        print(f"\n[{idx}] {news_time}: {headline[:80]}")
        
        prompt = f"""
        You are an elite quantitative portfolio manager at a top-tier Indian hedge fund. 
        Analyze this historical Indian market news from exactly {news_time}:
        '{headline}'

        CRITICAL RULES FOR HIGH WIN RATE:
        1. If the news is ambiguous, already priced in, or has low direct impact on any specific stock, DO NOT FORCE A TRADE. Return empty array.
        2. Only recommend stocks when there is a CLEAR, UNDENIABLE directional edge.
        3. Maximum 1-2 stocks.
        4. Think about 2nd/3rd order effects.
        5. 'confidence': integer 0-100.
        Output STRICTLY as JSON:
        {{
          "affected_stocks": [
            {{
                "ticker": "TICKER.NS",
                "predicted_impact": "bullish" | "bearish",
                "confidence": 85,
                "reason": "Clear 1-sentence reason"
            }}
          ]
        }}
        """
        try:
            r = backtest.client.models.generate_content(
                model=backtest.MODEL_NAME,
                contents=prompt,
                config=backtest.types.GenerateContentConfig(response_mime_type="application/json")
            )
            analysis = backtest.clean_json(r.text)
            stocks = analysis.get('affected_stocks', [])
            
            if not stocks:
                print("  -> AI: No stocks found or confidence too low.")
                continue
                
            for stock in stocks:
                ticker = stock['ticker']
                impact = stock['predicted_impact']
                conf = stock['confidence']
                print(f"  -> AI Prediction: {ticker} {impact} (Conf: {conf})")
                print(f"     Reason: {stock.get('reason')}")
                
                # Fetch TA and scan
                res, pct, day = backtest.scan_candles_for_result(ticker, news_time, impact)
                print(f"     => Result: {res} at Day {day} (Pct: {pct}%)")

        except Exception as e:
            print("  -> API Error:", e)

if __name__ == '__main__':
    quick_analyze()

