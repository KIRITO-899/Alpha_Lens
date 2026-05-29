import sqlite3
import json
from datetime import datetime, timedelta, timezone

db_path = "backend/news_cache.db"

# USDINR shock
usdinr_ripple = {
  "event_id": 1,
  "instrument": "US Dollar / Indian Rupee",
  "symbol": "USDINR",
  "shock_level": "Significant",
  "change_pct_1d": 1.25,
  "summary": "USD/INR has breached the +1.2% threshold today. This triggers a ripple effect on export-oriented and import-heavy sectors.",
  "tiers": [
    {
      "tier": 1,
      "nodes": [
        {
          "ticker": "INFY.NS",
          "direction": "BULLISH",
          "confidence": 85,
          "reason": "IT services benefit from USD strengthening (higher export revenue translation)."
        },
        {
          "ticker": "TCS.NS",
          "direction": "BULLISH",
          "confidence": 80,
          "reason": "USD appreciation improves margins for major exporters."
        },
        {
          "ticker": "BPCL.NS",
          "direction": "BEARISH",
          "confidence": 75,
          "reason": "Oil marketing companies face higher crude import costs due to rupee depreciation."
        }
      ]
    },
    {
      "tier": 2,
      "nodes": [
        {
          "ticker": "WIPRO.NS",
          "direction": "BULLISH",
          "confidence": 70,
          "reason": "Correlated IT spending sentiment aligns with sector leaders."
        }
      ]
    }
  ]
}

# Brent Crude shock
brent_ripple = {
  "event_id": 2,
  "instrument": "Brent Crude Oil",
  "symbol": "Brent Crude",
  "shock_level": "Major",
  "change_pct_1d": -3.85,
  "summary": "Brent Crude fell -3.85% following production increases. This reduces input cost pressures for paints, tires, and aviation sectors.",
  "tiers": [
    {
      "tier": 1,
      "nodes": [
        {
          "ticker": "ASIANPAINT.NS",
          "direction": "BULLISH",
          "confidence": 90,
          "reason": "Paints use crude oil derivatives for 50%+ of raw materials. Cost reductions boost gross margins."
        },
        {
          "ticker": "MRF.NS",
          "direction": "BULLISH",
          "confidence": 82,
          "reason": "Tire makers benefit from lower carbon black and synthetic rubber (crude-derived) costs."
        },
        {
          "ticker": "ONGC.NS",
          "direction": "BEARISH",
          "confidence": 88,
          "reason": "Oil exploration profits shrink directly due to lower realization per barrel."
        }
      ]
    }
  ]
}

def seed():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check schema
    c.execute("PRAGMA table_info(macro_event)")
    cols = [r[1] for r in c.fetchall()]
    print("Columns in macro_event:", cols)
    
    # Delete old events
    c.execute("DELETE FROM macro_event")
    
    # Create insert query
    query = """
    INSERT INTO macro_event 
    (instrument_key, instrument_label, symbol, shock_level, change_pct_1d, last_price, prev_close, ripple_json, expires_at, detected_at, during_nse_hours)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    now_utc = datetime.now(timezone.utc)
    detected_at = now_utc.strftime('%Y-%m-%d %H:%M:%S')
    expires_at = (now_utc + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Insert USDINR
    c.execute(query, (
        "USDINR", 
        "US Dollar / Indian Rupee", 
        "USDINR", 
        "Significant", 
        1.25, 
        83.45, 
        82.42, 
        json.dumps(usdinr_ripple), 
        expires_at, 
        detected_at, 
        0
    ))
    
    # Insert Brent Crude
    c.execute(query, (
        "BRENT", 
        "Brent Crude Oil", 
        "Brent Crude", 
        "Major", 
        -3.85, 
        78.40, 
        81.54, 
        json.dumps(brent_ripple), 
        expires_at, 
        detected_at, 
        0
    ))
    
    conn.commit()
    print("Successfully seeded 2 mock macro events!")
    
    c.execute("SELECT id, instrument_key, expires_at FROM macro_event")
    print("Stored rows:", c.fetchall())
    conn.close()

if __name__ == "__main__":
    seed()
