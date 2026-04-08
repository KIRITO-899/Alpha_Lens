"""
Technical Analysis Helper Module for Alpha Lens.
Provides market context data to feed into AI prompts for better predictions.
"""
import yfinance as yf
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('yfinance')
logger.disabled = True
logger.propagate = False


def compute_rsi(closes, period=14):
    """Compute RSI (Relative Strength Index) from a list/series of closing prices."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_sma(closes, period):
    """Compute Simple Moving Average for the last `period` data points."""
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def compute_bollinger_position(closes, period=20):
    """
    Returns where the current price sits relative to Bollinger Bands.
    Returns a value: <0 means below lower band, >1 means above upper band,
    0.5 means at the middle (SMA).
    """
    if len(closes) < period:
        return None
    sma = sum(closes[-period:]) / period
    std = (sum((c - sma) ** 2 for c in closes[-period:]) / period) ** 0.5
    if std == 0:
        return 0.5
    upper = sma + 2 * std
    lower = sma - 2 * std
    band_width = upper - lower
    if band_width == 0:
        return 0.5
    return round((closes[-1] - lower) / band_width, 2)


def get_stock_technical_context(ticker, lookback_days=60):
    """
    Fetch comprehensive technical context for a stock ticker.
    Returns a dict with all technical indicators, or None if data unavailable.
    """
    try:
        if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
            ticker += '.NS'

        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{lookback_days}d")

        if hist.empty or len(hist) < 20:
            return None

        closes = hist['Close'].tolist()
        volumes = hist['Volume'].tolist()
        current_price = round(closes[-1], 2)

        # Price returns
        ret_1d = round(((closes[-1] - closes[-2]) / closes[-2]) * 100, 2) if len(closes) >= 2 else 0
        ret_5d = round(((closes[-1] - closes[-6]) / closes[-6]) * 100, 2) if len(closes) >= 6 else 0
        ret_20d = round(((closes[-1] - closes[-21]) / closes[-21]) * 100, 2) if len(closes) >= 21 else 0

        # 52-week high/low (use available data)
        high_52w = round(max(hist['High'].tolist()), 2)
        low_52w = round(min(hist['Low'].tolist()), 2)
        range_52w = high_52w - low_52w
        pct_from_high = round(((current_price - high_52w) / high_52w) * 100, 2) if high_52w > 0 else 0
        pct_from_low = round(((current_price - low_52w) / low_52w) * 100, 2) if low_52w > 0 else 0

        # Position in 52w range (0 = at low, 1 = at high)
        range_position = round((current_price - low_52w) / range_52w, 2) if range_52w > 0 else 0.5

        # RSI
        rsi = compute_rsi(closes, 14)

        # Moving Averages
        sma_20 = compute_sma(closes, 20)
        sma_50 = compute_sma(closes, min(50, len(closes)))

        # Price vs SMA signals
        above_sma20 = current_price > sma_20 if sma_20 else None
        above_sma50 = current_price > sma_50 if sma_50 else None

        # Volume analysis
        avg_volume_20d = round(sum(volumes[-20:]) / 20) if len(volumes) >= 20 else round(sum(volumes) / len(volumes))
        latest_volume = volumes[-1]
        volume_ratio = round(latest_volume / avg_volume_20d, 2) if avg_volume_20d > 0 else 1.0

        # Bollinger Band position
        bb_position = compute_bollinger_position(closes, 20)

        # Trend determination
        if sma_20 and sma_50:
            if sma_20 > sma_50 and current_price > sma_20:
                trend = "STRONG_UPTREND"
            elif sma_20 > sma_50:
                trend = "UPTREND"
            elif sma_20 < sma_50 and current_price < sma_20:
                trend = "STRONG_DOWNTREND"
            elif sma_20 < sma_50:
                trend = "DOWNTREND"
            else:
                trend = "SIDEWAYS"
        else:
            trend = "UNKNOWN"

        # Overbought / Oversold determination
        if rsi is not None:
            if rsi > 75:
                momentum_signal = "OVERBOUGHT"
            elif rsi > 60:
                momentum_signal = "BULLISH_MOMENTUM"
            elif rsi < 25:
                momentum_signal = "OVERSOLD"
            elif rsi < 40:
                momentum_signal = "BEARISH_MOMENTUM"
            else:
                momentum_signal = "NEUTRAL"
        else:
            momentum_signal = "UNKNOWN"

        return {
            "ticker": ticker,
            "current_price": current_price,
            "return_1d_pct": ret_1d,
            "return_5d_pct": ret_5d,
            "return_20d_pct": ret_20d,
            "rsi_14": rsi,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "above_sma20": above_sma20,
            "above_sma50": above_sma50,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "pct_from_52w_high": pct_from_high,
            "pct_from_52w_low": pct_from_low,
            "range_position_52w": range_position,
            "volume_ratio_vs_20d_avg": volume_ratio,
            "bollinger_position": bb_position,
            "trend": trend,
            "momentum_signal": momentum_signal
        }
    except Exception as e:
        return None


def get_market_regime():
    """
    Determine the overall market regime by analyzing NIFTY 50.
    Returns: 'RISK_ON', 'RISK_OFF', or 'NEUTRAL'
    """
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="30d")
        if hist.empty or len(hist) < 10:
            return "UNKNOWN"

        closes = hist['Close'].tolist()
        ret_5d = ((closes[-1] - closes[-6]) / closes[-6]) * 100 if len(closes) >= 6 else 0
        rsi = compute_rsi(closes, 14)

        if ret_5d > 2 and rsi and rsi > 55:
            return "RISK_ON"
        elif ret_5d < -2 and rsi and rsi < 45:
            return "RISK_OFF"
        else:
            return "NEUTRAL"
    except:
        return "UNKNOWN"


def format_technical_context_for_prompt(tech_data):
    """
    Format technical data into a concise string for inclusion in the AI prompt.
    """
    if tech_data is None:
        return "Technical data unavailable."

    lines = [
        f"Ticker: {tech_data['ticker']}",
        f"Current Price: ₹{tech_data['current_price']}",
        f"1-Day Return: {tech_data['return_1d_pct']}% | 5-Day Return: {tech_data['return_5d_pct']}% | 20-Day Return: {tech_data['return_20d_pct']}%",
        f"RSI(14): {tech_data['rsi_14']} ({tech_data['momentum_signal']})",
        f"SMA20: ₹{tech_data['sma_20']} (Price {'above' if tech_data['above_sma20'] else 'below'}) | SMA50: ₹{tech_data['sma_50']}",
        f"52W Range: ₹{tech_data['low_52w']} - ₹{tech_data['high_52w']} | Position: {tech_data['range_position_52w']} (0=low, 1=high)",
        f"From 52W High: {tech_data['pct_from_52w_high']}% | From 52W Low: {tech_data['pct_from_52w_low']}%",
        f"Volume vs 20D Avg: {tech_data['volume_ratio_vs_20d_avg']}x",
        f"Bollinger Position: {tech_data['bollinger_position']} (0=lower band, 1=upper band)",
        f"Overall Trend: {tech_data['trend']}"
    ]
    return "\n".join(lines)


def get_batch_technical_context(tickers, lookback_days=60):
    """Fetch technical context for multiple tickers at once."""
    results = {}
    for ticker in tickers:
        results[ticker] = get_stock_technical_context(ticker, lookback_days)
    return results
