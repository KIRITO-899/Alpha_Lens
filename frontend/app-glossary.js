/* ===========================================================================
 * app-glossary.js  (chunk 12/12)  —  BEGINNER EXPLAIN-LAYER
 *
 * A deterministic TERM -> {term, short, long} glossary + ONE delegated tooltip
 * for any element carrying class "gloss" (data-term="<key>"). No LLM, no network
 * — same spirit as the filings click-to-explain. Hover (desktop) or tap (mobile)
 * a faint dotted term to learn what it means. Classic script, shared global scope.
 *
 * Usage from any other chunk's render code:
 *     glossTerm('PCR')            -> '<span class="gloss" data-term="pcr">PCR ?</span>'
 *     glossTerm('Max Pain','max_pain')
 * If the key isn't in the map, it falls back to the plain (escaped) label.
 * ======================================================================== */

const JARGON = {
  pcr: { term: 'PCR — Put/Call Ratio',
    short: 'Put open-interest ÷ call open-interest.',
    long: 'Compares how many put options are open vs calls. High (>1.2) leans bullish (heavy put-writing acts as support); low (<0.8) leans bearish (heavy call-writing caps the move). A crowd-positioning gauge, not a guarantee.' },
  max_pain: { term: 'Max Pain',
    short: 'The strike where option BUYERS lose the most at expiry.',
    long: 'The price level where the largest rupee value of options expires worthless — option buyers lose most, writers gain most. Price often drifts toward it near expiry because large writers are incentivised to keep it there.' },
  call_wall: { term: 'Call Wall (Resistance)',
    short: 'Strike with the biggest call open-interest.',
    long: 'The strike carrying the most call writing — it tends to act as a ceiling/resistance, since writers defend it. A move above a fresh call wall can trigger short-covering.' },
  put_wall: { term: 'Put Wall (Support)',
    short: 'Strike with the biggest put open-interest.',
    long: 'The strike carrying the most put writing — it tends to act as a floor/support, since put writers defend it. A break below it can accelerate selling.' },
  atm_iv: { term: 'ATM Implied Volatility',
    short: 'The market’s expected volatility at the at-the-money strike.',
    long: 'Implied volatility of the option nearest the current price — how much movement the market is pricing in. High IV = expensive options (favours spreads/selling premium); low IV = cheap options (favours buying).' },
  iv_skew: { term: 'IV Skew (Put − Call)',
    short: 'Downside IV minus upside IV.',
    long: 'IV of an out-of-the-money put minus an out-of-the-money call. Positive skew means traders are paying up for downside protection (fear); negative means upside calls are bid (greed).' },
  basis: { term: 'Futures Basis',
    short: 'Futures price minus spot price (%).',
    long: 'How far the future trades above (premium) or below (discount) the cash price. A widening premium signals bullish carry/positioning; a discount can signal bearishness or dividend/cost effects.' },
  rollover: { term: 'Rollover %',
    short: 'Share of open interest moving to the next expiry.',
    long: 'Of the total futures open interest, how much sits in the next month vs the front month. High rollover = traders carrying positions forward (conviction); low = positions being closed.' },
  open_interest: { term: 'Open Interest (OI)',
    short: 'Total outstanding (not-yet-closed) derivative contracts.',
    long: 'The number of futures/options contracts currently open. Rising OI = fresh money entering a move; falling OI = positions being unwound. Combined with price it reveals what big players are doing.' },
  oi_buildup: { term: 'OI Buildup',
    short: 'What price + open-interest together say about positioning.',
    long: 'Reading price and OI together: price↑ + OI↑ = Long Buildup (fresh bulls); price↓ + OI↑ = Short Buildup (fresh bears); price↑ + OI↓ = Short Covering; price↓ + OI↓ = Long Unwinding.' },
  long_buildup: { term: 'Long Buildup',
    short: 'Price up + open-interest up = fresh bullish bets.',
    long: 'New long positions are being added as the price rises — the strongest bullish footprint, since fresh money is backing the up-move.' },
  short_buildup: { term: 'Short Buildup',
    short: 'Price down + open-interest up = fresh bearish bets.',
    long: 'New short positions are being added as the price falls — the strongest bearish footprint, since fresh money is backing the down-move.' },
  short_covering: { term: 'Short Covering',
    short: 'Price up + open-interest down = bears exiting.',
    long: 'A rise driven by shorts buying back to close, not fresh buying — often a sharp but less durable bounce than a long buildup.' },
  long_unwinding: { term: 'Long Unwinding',
    short: 'Price down + open-interest down = bulls exiting.',
    long: 'A fall driven by longs closing out, not fresh shorting — weakening momentum rather than aggressive new bearishness.' },
  unusual_oi: { term: 'Unusual OI Surge',
    short: 'An abnormally large 1-day jump in open interest.',
    long: 'Open interest jumped far more than normal in a single session (≥18%) — a sign of fresh, aggressive positioning worth a closer look.' },
  delivery: { term: 'Delivery %',
    short: 'Share of traded shares actually taken for delivery.',
    long: 'Of all shares traded, how many were taken to demat (not intraday-squared-off). High delivery (>55%) signals genuine accumulation by longer-term buyers rather than day-trading churn.' },
  fii_dii: { term: 'FII / DII',
    short: 'Foreign vs domestic institutional investors.',
    long: 'FII = Foreign Institutional Investors (global funds); DII = Domestic Institutional Investors (Indian MFs/insurers). Their net buying/selling is the single most-watched institutional flow.' },
  india_vix: { term: 'India VIX',
    short: 'The market’s expected 30-day volatility (“fear gauge”).',
    long: 'A live index of expected near-term Nifty volatility from option prices. Rising VIX (>18) = fear/uncertainty; low VIX (<12) = complacency/calm.' },
  conviction: { term: 'Conviction Score',
    short: 'How strongly the data backs this read (0–99).',
    long: 'A deterministic blend of OI-surge size, directional price confirmation, liquidity and delivery — higher means the footprint is bigger and cleaner. It measures signal strength, not a price target.' },
  bias_score: { term: 'Bias Score',
    short: 'Net long vs short pressure across F&O (−100…+100).',
    long: 'A conviction-weighted tally of bullish vs bearish buildups across the F&O universe, overlaid with index PCR. Positive = the tape leans long; negative = leans short.' },
  atr: { term: 'ATR (Average True Range)',
    short: 'A volatility-based measure of a stock’s typical move.',
    long: 'The average size of a stock’s daily range. Signal targets/stops are set as multiples of ATR so they adapt to each stock’s volatility instead of a fixed %.' },
  hit_rate: { term: 'Hit Rate',
    short: 'Share of closed signals that reached their target first.',
    long: 'Of signals that have finished (hit target or stop, or expired), the % that hit the target before the stop. Only shown once trades close — open signals don’t count.' },
  risk_regime: { term: 'Risk On / Risk Off',
    short: 'Whether the broad market is in a risk-taking mood.',
    long: 'A read of the overall market regime: Risk-On = breadth/momentum favour buying; Risk-Off = defensive, counter-trend signals are penalised.' },
  delta: { term: 'Delta',
    short: 'How much an option moves per ₹1 move in the stock.',
    long: 'The option’s sensitivity to the underlying: a 0.5 delta call gains ~₹0.50 for each ₹1 the stock rises. Also a rough probability the option finishes in-the-money.' },
};

function _glossKey(t) {
  return String(t || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
}

// Render a term with a faint dotted underline + a "?" affordance the tooltip reads.
// Falls back to the plain escaped label when the key isn't in the glossary.
function glossTerm(label, key) {
  const k = key || _glossKey(label);
  const esc = (typeof escapeHtml === 'function') ? escapeHtml : (s) => String(s == null ? '' : s);
  if (!JARGON[k]) return esc(label);
  return `<span class="gloss" data-term="${k}" tabindex="0" role="button" aria-label="${esc(label)} — what's this?" onclick="event.stopPropagation();glossToggle(this)">${esc(label)}<span class="gloss-q">?</span></span>`;
}
window.glossTerm = glossTerm;

// ── one delegated tooltip for every .gloss on the page ──────────────────────
(function _glossInit() {
  let tip = null;
  function ensure() {
    if (tip) return tip;
    tip = document.createElement('div');
    tip.className = 'gloss-tip hidden';
    tip.setAttribute('role', 'tooltip');
    document.body.appendChild(tip);
    return tip;
  }
  function show(el) {
    const g = JARGON[el.getAttribute('data-term')];
    if (!g) return;
    const t = ensure();
    const esc = (typeof escapeHtml === 'function') ? escapeHtml : (s) => String(s == null ? '' : s);
    t.innerHTML = `<div class="gloss-tip-term">${esc(g.term)}</div><div class="gloss-tip-long">${esc(g.long || g.short || '')}</div>`;
    t._for = el;
    t.classList.remove('hidden');
    const r = el.getBoundingClientRect();
    const tw = t.offsetWidth, th = t.offsetHeight;
    let left = r.left + r.width / 2 - tw / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - tw - 8));
    let top = r.top - th - 8;
    if (top < 8) top = r.bottom + 8;
    t.style.left = left + 'px';
    t.style.top = top + 'px';
  }
  function hide() { if (tip) { tip.classList.add('hidden'); tip._for = null; } }
  window.glossToggle = function (el) {
    if (tip && tip._for === el && !tip.classList.contains('hidden')) hide();
    else show(el);
  };
  document.addEventListener('mouseover', (e) => { const el = e.target.closest && e.target.closest('.gloss'); if (el) show(el); });
  document.addEventListener('mouseout', (e) => { const el = e.target.closest && e.target.closest('.gloss'); if (el) hide(); });
  document.addEventListener('click', (e) => { if (!(e.target.closest && e.target.closest('.gloss'))) hide(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
  window.addEventListener('scroll', hide, { passive: true });
})();
