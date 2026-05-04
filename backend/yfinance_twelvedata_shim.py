import pandas as pd
import requests
import logging
from datetime import datetime

# Disable logging spam matching yfinance
logger = logging.getLogger('yfinance_twelvedata_shim')
logger.disabled = True
logger.propagate = False

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# TwelveData key is optional — Yahoo Finance fallback works without any key
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY") or os.environ.get("TWELVEDATA_API_KEY")

def set_tz_cache_location(*args, **kwargs):
    pass

class FastInfo:
    def __init__(self, last_price, previous_close, day_high, day_low):
        self.last_price = last_price
        self.previous_close = previous_close
        self.day_high = day_high
        self.day_low = day_low

def _twelve_to_yf_ticker(ticker):
    """Convert yfinance-style ticker to TwelveData format."""
    if isinstance(ticker, str):
        if ticker.endswith(".NS"):
            return f"{ticker[:-3]}:NSE"
        elif ticker.endswith(".BO"):
            return f"{ticker[:-3]}:BSE"
        if ticker == "^NSEI":
            return "NIFTY 50:NSE"
        elif ticker == "^BSESN":
            return "SENSEX:BSE"
        elif ticker == "^NSEBANK":
            return "NIFTY BANK:NSE"
        elif ticker == "^NSMIDCP":
            return "NIFTY MIDCAP 50:NSE"
    return ticker

# ─────────────────────────────────────────────────────────────────
# Yahoo Finance direct API — no API key required
# ─────────────────────────────────────────────────────────────────
_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def _yahoo_get_quote(ticker):
    """Fetch last_price and previous_close from Yahoo Finance chart API. No key needed."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"
        resp = requests.get(url, headers=_YF_HEADERS, timeout=8)
        data = resp.json()
        result = data.get('chart', {}).get('result', [{}])[0]
        meta = result.get('meta', {})
        last_price = meta.get('regularMarketPrice') or meta.get('previousClose')
        prev_close = meta.get('chartPreviousClose') or meta.get('previousClose')

        # Fallback to close series if meta is incomplete
        if not last_price:
            closes = [c for c in (result.get('indicators', {}).get('quote', [{}])[0].get('close', [])) if c]
            if closes:
                last_price = closes[-1]
                if len(closes) >= 2 and not prev_close:
                    prev_close = closes[-2]

        lp = float(last_price) if last_price else 0.0
        pc = float(prev_close) if prev_close else lp
        return lp, pc
    except Exception:
        return 0.0, 0.0

def _yahoo_get_history(ticker, period='5d', interval='1d'):
    """Fetch OHLCV history from Yahoo Finance chart API. No key needed."""
    period_map = {'1d': '1d', '2d': '5d', '5d': '5d', '7d': '1mo', '1mo': '3mo', '3mo': '6mo'}
    interval_map = {'1d': '1d', '1m': '1m', '5m': '5m', '15m': '15m', '60m': '60m'}
    yf_range = period_map.get(period, '1mo')
    yf_interval = interval_map.get(interval, '1d')
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={yf_range}&interval={yf_interval}"
        resp = requests.get(url, headers=_YF_HEADERS, timeout=10)
        data = resp.json()
        result = data.get('chart', {}).get('result', [{}])[0]
        timestamps = result.get('timestamp', [])
        quotes = result.get('indicators', {}).get('quote', [{}])[0]
        if not timestamps or not quotes:
            return pd.DataFrame()

        df = pd.DataFrame({
            'Open':   quotes.get('open', []),
            'High':   quotes.get('high', []),
            'Low':    quotes.get('low', []),
            'Close':  quotes.get('close', []),
            'Volume': quotes.get('volume', []),
        }, index=pd.to_datetime(timestamps, unit='s', utc=True))

        df = df.dropna(subset=['Close'])
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df
    except Exception:
        return pd.DataFrame()


class Ticker:
    def __init__(self, ticker):
        self.ticker = ticker
        self.td_ticker = _twelve_to_yf_ticker(ticker)
        self._quote = None

    def _fetch_quote(self):
        # Try TwelveData first if key is available
        if TWELVE_DATA_API_KEY:
            try:
                url = f"https://api.twelvedata.com/quote?symbol={self.td_ticker}&apikey={TWELVE_DATA_API_KEY}"
                resp = requests.get(url, timeout=5)
                q = resp.json()
                if q.get('status') != 'error' and 'close' in q:
                    self._quote = q
                    return
            except Exception:
                pass

        # Fallback: Yahoo Finance (no key needed)
        lp, pc = _yahoo_get_quote(self.ticker)
        self._quote = {
            'close': lp,
            'previous_close': pc,
            'high': lp,
            'low': lp,
            '_from_yahoo': True
        }

    @property
    def fast_info(self):
        if not self._quote:
            self._fetch_quote()

        if not self._quote or (self._quote.get('status') == 'error' and not self._quote.get('_from_yahoo')):
            lp, pc = _yahoo_get_quote(self.ticker)
            return FastInfo(lp, pc, lp, lp)

        try:
            lp = float(self._quote.get('close', 0.0))
            pc = float(self._quote.get('previous_close', lp))
            dh = float(self._quote.get('high', lp))
            dl = float(self._quote.get('low', lp))
            return FastInfo(lp, pc, dh, dl)
        except Exception:
            lp, pc = _yahoo_get_quote(self.ticker)
            return FastInfo(lp, pc, lp, lp)

    def history(self, period="2d", interval="1d"):
        # Try TwelveData first if key available
        if TWELVE_DATA_API_KEY:
            if period.endswith('d'):
                try:
                    out_size = max(1, int(period[:-1])) * 2
                except:
                    out_size = 5
            elif 'mo' in period:
                out_size = 60
            else:
                out_size = 20

            td_interval = interval
            if td_interval == "1d":
                td_interval = "1day"
            elif td_interval == "1m":
                td_interval = "1min"
            elif td_interval.endswith("m"):
                td_interval = td_interval + "in"

            try:
                url = f"https://api.twelvedata.com/time_series?symbol={self.td_ticker}&interval={td_interval}&outputsize={out_size}&apikey={TWELVE_DATA_API_KEY}"
                resp = requests.get(url, timeout=10).json()
                if resp.get('status') != 'error' and resp.get('values'):
                    values = resp['values']
                    values.reverse()
                    df = pd.DataFrame(values)
                    df['datetime'] = pd.to_datetime(df['datetime'])
                    df.set_index('datetime', inplace=True)
                    df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
                    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                        if col in df.columns:
                            df[col] = df[col].astype(float)
                    return df
            except Exception:
                pass

        # Fallback: Yahoo Finance history
        return _yahoo_get_history(self.ticker, period=period, interval=interval)


def download(tickers, period="7d", interval="1m", progress=False, auto_adjust=True):
    is_str = isinstance(tickers, str)
    ticker_list = [tickers] if is_str else tickers

    # Try TwelveData first if key available
    if TWELVE_DATA_API_KEY:
        td_interval = interval
        if td_interval == "1d":
            td_interval = "1day"
        elif td_interval == "1m":
            td_interval = "1min"
        elif td_interval.endswith("m"):
            td_interval = td_interval + "in"

        try:
            td_ticker = _twelve_to_yf_ticker(ticker_list[0])
            url = f"https://api.twelvedata.com/time_series?symbol={td_ticker}&interval={td_interval}&outputsize=2500&apikey={TWELVE_DATA_API_KEY}"
            resp = requests.get(url, timeout=10).json()
            if resp.get('status') != 'error' and resp.get('values'):
                values = resp['values']
                values.reverse()
                df = pd.DataFrame(values)
                df['datetime'] = pd.to_datetime(df['datetime'])
                df.set_index('datetime', inplace=True)
                df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df.columns:
                        df[col] = df[col].astype(float)
                return df
        except Exception:
            pass

    # Fallback: Yahoo Finance
    return _yahoo_get_history(ticker_list[0], period=period, interval=interval)


# Compatibility alias
Ticker.FastInfo = FastInfo
