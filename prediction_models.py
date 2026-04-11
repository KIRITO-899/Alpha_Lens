"""
Alpha Lens v4.0 — Multi-Model Ensemble Prediction Engine
5 independent models analyze news → stock impact.
Signal emitted ONLY when ensemble score >= 70 AND 3+ models agree.
"""
import re
import math

# ==========================================
# MODEL 1: SENTIMENT DEPTH ANALYSIS
# ==========================================
class SentimentDepthModel:
    """Analyzes headline sentiment intensity — keyword strength, negation, percentage modifiers."""
    
    STRONG_BULLISH = ['surge', 'surges', 'soar', 'soars', 'zoom', 'zooms', 'skyrocket',
                      'doubles', 'triples', 'record high', 'all-time high', 'blockbuster',
                      'stellar', 'robust', 'massive', 'breakout', '52-week high']
    MILD_BULLISH = ['rise', 'rises', 'gain', 'gains', 'up ', 'high', 'positive',
                    'growth', 'profit', 'beat', 'rebound', 'recovery', 'dividend',
                    'upgrade', 'buy', 'bullish', 'outperform', 'optimistic', 'winner',
                    'top pick', 'expansion', 'recommend']
    STRONG_BEARISH = ['crash', 'crashes', 'plunge', 'plunges', 'collapse', 'tank', 'tanks',
                      'worst', 'crisis', 'scam', 'fraud', 'ban', 'default', 'bloodbath',
                      'meltdown', 'wipeout', 'halt', '52-week low']
    MILD_BEARISH = ['fall', 'falls', 'drop', 'drops', 'decline', 'declines', 'down ',
                    'loss', 'losses', 'weak', 'negative', 'concern', 'fear', 'sell',
                    'downgrade', 'underperform', 'miss', 'cut', 'cuts', 'slash', 'warning',
                    'flee', 'exit', 'outflow', 'slump']
    NEGATION = ['despite', 'but', 'however', 'although', 'even as', 'in spite of']
    INTENSITY = {'sharply': 1.5, 'significantly': 1.4, 'massively': 1.8, 'slightly': 0.5,
                 'marginally': 0.4, 'strongly': 1.5, 'heavily': 1.6, 'aggressively': 1.7}

    def score(self, headline, direction):
        """Returns 0-100. Higher = more confidence in the given direction."""
        h = ' ' + headline.lower() + ' '
        strong_bull = sum(2 for kw in self.STRONG_BULLISH if kw in h)
        mild_bull = sum(1 for kw in self.MILD_BULLISH if kw in h)
        strong_bear = sum(2 for kw in self.STRONG_BEARISH if kw in h)
        mild_bear = sum(1 for kw in self.MILD_BEARISH if kw in h)
        bull_total = strong_bull + mild_bull
        bear_total = strong_bear + mild_bear

        # Negation flips partial sentiment
        if any(neg in h for neg in self.NEGATION):
            bull_total, bear_total = bear_total * 0.6, bull_total * 0.6

        # Intensity multiplier
        intensity = max((mult for word, mult in self.INTENSITY.items() if word in h), default=1.0)

        # Percentage bonus
        pct_match = re.search(r'(\d+\.?\d*)%', headline)
        pct_bonus = min(15, float(pct_match.group(1)) * 2) if pct_match else 0

        total = bull_total + bear_total
        if total == 0:
            return 45

        alignment = (bull_total / total) if direction == 'BULLISH' else (bear_total / total)
        base = alignment * intensity * 70
        return max(20, min(95, int(base + pct_bonus)))


# ==========================================
# MODEL 2: HISTORICAL SIMILARITY
# ==========================================
class HistoricalSimilarityModel:
    """Finds similar past headlines and checks if those signals hit target or failed."""

    @staticmethod
    def _tokenize(text):
        return set(re.findall(r'[a-z]{3,}', text.lower()))

    @staticmethod
    def _similarity(s1, s2):
        if not s1 or not s2:
            return 0.0
        return len(s1 & s2) / len(s1 | s2)

    def score(self, headline, ticker, direction, db_connect_fn):
        """Returns 0-100 based on how similar past headlines performed."""
        try:
            conn = db_connect_fn()
            c = conn.cursor()
            c.execute("SELECT headline, direction, outcome FROM historical_patterns WHERE ticker = ?", (ticker,))
            patterns = c.fetchall()
            conn.close()

            if len(patterns) < 3:
                return 65  # Not enough data — neutral-high default

            tokens = self._tokenize(headline)
            matches = []
            for past_h, past_dir, outcome in patterns:
                sim = self._similarity(tokens, self._tokenize(past_h))
                if sim > 0.15:
                    matches.append({'sim': sim, 'same_dir': past_dir == direction, 'hit': outcome == 'HIT'})

            if not matches:
                return 65

            same_dir = [m for m in matches if m['same_dir']]
            if not same_dir:
                return 50

            weighted_hits = sum(m['sim'] for m in same_dir if m['hit'])
            weighted_total = sum(m['sim'] for m in same_dir)
            win_rate = weighted_hits / weighted_total if weighted_total > 0 else 0.5
            return max(30, min(95, int(win_rate * 100)))
        except Exception:
            return 65


# ==========================================
# MODEL 3: TECHNICAL ALIGNMENT
# ==========================================
class TechnicalAlignmentModel:
    """Checks if RSI, SMA, trend, volume support the predicted direction."""

    def score(self, tech_data, direction):
        """Returns 0-100 based on technical alignment."""
        if tech_data is None:
            return 50
        s = 50
        bull = (direction == 'BULLISH')
        rsi = tech_data.get('rsi_14')
        if rsi is not None:
            if bull:
                if rsi < 30: s += 15
                elif rsi < 45: s += 10
                elif rsi > 75: s -= 15
                elif rsi > 60: s += 5
            else:
                if rsi > 70: s += 15
                elif rsi > 55: s += 10
                elif rsi < 25: s -= 15
                elif rsi < 40: s += 5

        above_sma20 = tech_data.get('above_sma20')
        if above_sma20 is not None:
            s += 10 if (bull == above_sma20) else -10

        trend = tech_data.get('trend', '')
        if bull:
            if 'UPTREND' in trend: s += 10
            elif 'DOWNTREND' in trend: s -= 10
        else:
            if 'DOWNTREND' in trend: s += 10
            elif 'UPTREND' in trend: s -= 10

        vol = tech_data.get('volume_ratio_vs_20d_avg', 1.0)
        if vol > 1.5: s += 5
        elif vol < 0.5: s -= 5

        rp = tech_data.get('range_position_52w', 0.5)
        if bull and rp > 0.85: s -= 5
        elif bull and rp < 0.3: s += 5
        elif not bull and rp < 0.15: s -= 5
        elif not bull and rp > 0.7: s += 5

        momentum = tech_data.get('momentum_signal', '')
        if bull and momentum == 'BULLISH_MOMENTUM': s += 5
        elif not bull and momentum == 'BEARISH_MOMENTUM': s += 5

        return max(15, min(95, s))

    def has_veto(self, tech_data, direction):
        """True if technicals strongly contradict the direction."""
        if tech_data is None:
            return False
        bull = (direction == 'BULLISH')
        rsi = tech_data.get('rsi_14')
        above_sma20 = tech_data.get('above_sma20')
        rp = tech_data.get('range_position_52w', 0.5)
        if bull:
            if rsi and rsi > 80 and rp > 0.9: return True
            if above_sma20 is False and rsi and rsi < 30: return True
        else:
            if rsi and rsi < 20 and rp < 0.1: return True
            if above_sma20 is True and rsi and rsi > 70: return True
        return False


# ==========================================
# MODEL 4: SECTOR MOMENTUM
# ==========================================
class SectorMomentumModel:
    """Checks if stock's sector is trending in a direction that supports the prediction."""

    SECTOR_MAP = {
        'HDFCBANK.NS': '^NSEBANK', 'ICICIBANK.NS': '^NSEBANK', 'SBIN.NS': '^NSEBANK',
        'AXISBANK.NS': '^NSEBANK', 'KOTAKBANK.NS': '^NSEBANK', 'INDUSINDBK.NS': '^NSEBANK',
        'PNB.NS': '^NSEBANK', 'BANKBARODA.NS': '^NSEBANK', 'CANBK.NS': '^NSEBANK',
        'BAJFINANCE.NS': '^NSEBANK', 'BAJAJFINSV.NS': '^NSEBANK', 'CHOLAFIN.NS': '^NSEBANK',
        'SHRIRAMFIN.NS': '^NSEBANK', 'MUTHOOTFIN.NS': '^NSEBANK', 'MANAPPURAM.NS': '^NSEBANK',
        'BANDHANBNK.NS': '^NSEBANK', 'FEDERALBNK.NS': '^NSEBANK', 'YESBANK.NS': '^NSEBANK',
        'IDBI.NS': '^NSEBANK',

        'INFY.NS': '^CNXIT', 'TCS.NS': '^CNXIT', 'WIPRO.NS': '^CNXIT',
        'HCLTECH.NS': '^CNXIT', 'TECHM.NS': '^CNXIT', 'LTIM.NS': '^CNXIT',
        'PERSISTENT.NS': '^CNXIT', 'COFORGE.NS': '^CNXIT', 'MPHASIS.NS': '^CNXIT',

        'SUNPHARMA.NS': '^CNXPHARMA', 'CIPLA.NS': '^CNXPHARMA', 'DRREDDY.NS': '^CNXPHARMA',
        'DIVISLAB.NS': '^CNXPHARMA', 'AUROPHARMA.NS': '^CNXPHARMA', 'LUPIN.NS': '^CNXPHARMA',

        'TATAMOTORS.NS': '^CNXAUTO', 'MARUTI.NS': '^CNXAUTO', 'M&M.NS': '^CNXAUTO',
        'BAJAJ-AUTO.NS': '^CNXAUTO', 'HEROMOTOCO.NS': '^CNXAUTO', 'EICHERMOT.NS': '^CNXAUTO',

        'TATASTEEL.NS': '^CNXMETAL', 'JSWSTEEL.NS': '^CNXMETAL', 'HINDALCO.NS': '^CNXMETAL',
        'VEDL.NS': '^CNXMETAL', 'JINDALSTEL.NS': '^CNXMETAL', 'COALINDIA.NS': '^CNXMETAL',

        'RELIANCE.NS': '^CNXENERGY', 'ONGC.NS': '^CNXENERGY', 'BPCL.NS': '^CNXENERGY',
        'HINDPETRO.NS': '^CNXENERGY', 'IOC.NS': '^CNXENERGY',
        'NTPC.NS': '^CNXENERGY', 'POWERGRID.NS': '^CNXENERGY', 'TATAPOWER.NS': '^CNXENERGY',

        'HAL.NS': '^NSEI', 'BEL.NS': '^NSEI', 'BHARATFORG.NS': '^NSEI',
    }

    _cache = {}

    def _get_sector_ret(self, idx):
        import yfinance as yf
        if idx in self._cache:
            return self._cache[idx]
        try:
            hist = yf.Ticker(idx).history(period='10d')
            if hist.empty or len(hist) < 2:
                self._cache[idx] = 0
                return 0
            c = hist['Close'].tolist()
            r = ((c[-1] - c[0]) / c[0]) * 100
            self._cache[idx] = r
            return r
        except:
            self._cache[idx] = 0
            return 0

    def score(self, ticker, direction, market_regime):
        """Returns 0-100 based on sector alignment."""
        s = 50
        bull = (direction == 'BULLISH')
        idx = self.SECTOR_MAP.get(ticker)
        if idx:
            m = self._get_sector_ret(idx)
            if bull:
                if m > 2: s += 15
                elif m > 0.5: s += 8
                elif m < -2: s -= 12
                elif m < -0.5: s -= 5
            else:
                if m < -2: s += 15
                elif m < -0.5: s += 8
                elif m > 2: s -= 12
                elif m > 0.5: s -= 5

        if market_regime == "RISK_ON":
            s += 10 if bull else -10
        elif market_regime == "RISK_OFF":
            s += -10 if bull else 10

        return max(20, min(90, s))

    def clear_cache(self):
        self._cache = {}


# ==========================================
# MODEL 5: EVENT PATTERN RECOGNITION
# ==========================================
class EventPatternModel:
    """Classifies event type and applies known market behavior patterns."""

    PATTERNS = {
        'earnings_beat': {
            'kw': ['beat', 'beats', 'above estimate', 'profit rise', 'profit jump',
                   'profit surge', 'net profit', 'strong results', 'stellar',
                   'blockbuster', 'doubles', 'revenue growth', 'record profit',
                   'pat rise', 'pat jump'],
            'dir': 'BULLISH', 'base': 75},
        'earnings_miss': {
            'kw': ['miss', 'misses', 'below estimate', 'profit fall', 'profit drop',
                   'loss widens', 'net loss', 'revenue decline', 'weak results',
                   'disappointing', 'margin squeeze', 'margin pressure'],
            'dir': 'BEARISH', 'base': 72},
        'upgrade': {
            'kw': ['upgrade', 'buy rating', 'outperform', 'top pick',
                   'target raise', 'target hike', 'price target raise'],
            'dir': 'BULLISH', 'base': 68},
        'downgrade': {
            'kw': ['downgrade', 'sell rating', 'underperform', 'underweight',
                   'target cut', 'target slash', 'reduce rating'],
            'dir': 'BEARISH', 'base': 68},
        'insider_buy': {
            'kw': ['promoter buy', 'insider buy', 'bulk buy', 'stake increase', 'buyback'],
            'dir': 'BULLISH', 'base': 70},
        'insider_sell': {
            'kw': ['promoter sell', 'insider sell', 'stake sale', 'offload',
                   'fii sell', 'fii exit', 'fii flee', 'fpi sell'],
            'dir': 'BEARISH', 'base': 65},
        'merger': {
            'kw': ['merger', 'acquisition', 'acquire', 'takeover', 'buyout', 'joint venture'],
            'dir': 'BULLISH', 'base': 65},
        'reg_positive': {
            'kw': ['approval', 'clearance', 'license', 'nod', 'pli', 'subsidy', 'incentive'],
            'dir': 'BULLISH', 'base': 68},
        'reg_negative': {
            'kw': ['ban', 'penalty', 'fine', 'probe', 'investigation', 'sebi order',
                   'suspension', 'scam', 'fraud'],
            'dir': 'BEARISH', 'base': 72},
        'macro_up': {
            'kw': ['rate cut', 'stimulus', 'fii inflow', 'gdp growth', 'recovery', 'ceasefire'],
            'dir': 'BULLISH', 'base': 62},
        'macro_down': {
            'kw': ['rate hike', 'inflation surge', 'fii outflow', 'tariff',
                   'trade war', 'recession', 'geopolitical'],
            'dir': 'BEARISH', 'base': 62},
    }

    def score(self, headline, direction):
        """Returns 0-100 based on event pattern matching."""
        h = headline.lower()
        best, best_n = None, 0
        for p in self.PATTERNS.values():
            n = sum(1 for kw in p['kw'] if kw in h)
            if n > best_n:
                best_n, best = n, p
        if not best or best_n == 0:
            return 55
        if direction == best['dir']:
            return min(90, best['base'] + best_n * 5)
        else:
            return max(25, best['base'] - best_n * 10)


# ==========================================
# ENSEMBLE COMBINER
# ==========================================
class EnsemblePredictor:
    """
    Combines all 5 models. Signal only emitted when:
      - Ensemble score >= 70                                    
      - At least 3 of 5 models agree (score > 55)
      - Technical model does NOT veto
    """

    WEIGHTS = {'sentiment': 0.20, 'historical': 0.25, 'technical': 0.25,
               'sector': 0.15, 'event': 0.15}

    def __init__(self):
        self.m1 = SentimentDepthModel()
        self.m2 = HistoricalSimilarityModel()
        self.m3 = TechnicalAlignmentModel()
        self.m4 = SectorMomentumModel()
        self.m5 = EventPatternModel()

    def predict(self, headline, ticker, direction, tech_data, market_regime,
                db_connect_fn, min_score=70):
        s1 = self.m1.score(headline, direction)
        s2 = self.m2.score(headline, ticker, direction, db_connect_fn)
        s3 = self.m3.score(tech_data, direction)
        s4 = self.m4.score(ticker, direction, market_regime)
        s5 = self.m5.score(headline, direction)

        final = int(
            s1 * self.WEIGHTS['sentiment'] +
            s2 * self.WEIGHTS['historical'] +
            s3 * self.WEIGHTS['technical'] +
            s4 * self.WEIGHTS['sector'] +
            s5 * self.WEIGHTS['event']
        )

        agree = sum(1 for s in [s1, s2, s3, s4, s5] if s > 55)
        veto = self.m3.has_veto(tech_data, direction)
        approved = final >= min_score and agree >= 3 and not veto

        detail_str = f"S:{s1} H:{s2} T:{s3} Sec:{s4} E:{s5} | {agree}/5 agree | {'VETO' if veto else 'OK'}"
        return {
            'approved': approved,
            'final_score': final,
            'direction': direction,
            'models_agreeing': agree,
            'has_veto': veto,
            'detail': detail_str,
            'scores': {'sentiment': s1, 'historical': s2, 'technical': s3,
                       'sector': s4, 'event': s5},
        }

    def clear_caches(self):
        self.m4.clear_cache()
