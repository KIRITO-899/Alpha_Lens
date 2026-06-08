/* ===========================================================================
 * app-filings.js  (chunk 11/11)  —  EXCHANGE FILING ALERTS
 *
 * Renders the "Exchange Filing Alerts" feed: material corporate filings
 * (promoter pledge, insider buy/sell, resignations, acquisitions, order wins,
 * rating changes, dividends, splits, bonuses) classified into plain-English,
 * normal-investor-friendly alerts.
 *
 * Data: GET /api/filings?type=<key>&limit=N  (deterministic, no LLM).
 * Lazy-loaded by switchTab('filings'). Classic script sharing the global scope.
 * ======================================================================== */

let _filData = null;
let _filLastFetch = 0;
let _filLoading = false;
let _filActiveType = 'all';
let _filRendered = [];            // the currently-rendered (filtered) feed, for the click modal
const _FIL_THROTTLE_MS = 60000;   // client throttle over the server cache

// ── per-type icons (inline SVG, 14×14, currentColor) ──────────────────────
const _FIL_ICONS = {
    promoter_pledge: '<path d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z"/>',
    insider_trading: '<path d="M3 12s3-7 9-7 9 7 9 7-3 7-9 7-9-7-9-7z"/><circle cx="12" cy="12" r="2.5"/>',
    rating_change:   '<path d="M3 17l6-6 4 4 7-7"/><path d="M14 8h6v6"/>',
    acquisition:     '<path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/><rect x="3" y="7" width="18" height="13" rx="2"/>',
    resignation:     '<path d="M16 17l5-5-5-5"/><path d="M21 12H9"/><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/>',
    order_win:       '<path d="M20 6L9 17l-5-5"/>',
    bonus:           '<path d="M20 12v9H4v-9"/><path d="M2 7h20v5H2z"/><path d="M12 22V7"/><path d="M12 7S9 2 6.5 4 12 7 12 7zM12 7s3-5 5.5-3S12 7 12 7z"/>',
    split:           '<path d="M3 12h18"/><path d="M7 8l-4 4 4 4"/><path d="M17 8l4 4-4 4"/>',
    dividend:        '<circle cx="12" cy="12" r="9"/><path d="M12 7v10M9.5 9.5h3.5a2 2 0 010 4H10"/>',
};
function _filIcon(type) {
    const inner = _FIL_ICONS[type] || '<circle cx="12" cy="12" r="9"/>';
    return `<svg class="fil-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
}

function _filImpactMeta(impact) {
    if (impact === 'positive') return { label: 'Positive', cls: 'imp-pos' };
    if (impact === 'negative') return { label: 'Negative', cls: 'imp-neg' };
    return { label: 'Neutral', cls: 'imp-neu' };
}

function _filAgo(ms) {
    ms = Number(ms || 0);
    if (!ms) return '';
    const s = Math.floor((Date.now() - ms) / 1000);
    if (s < 0) return 'just now';
    if (s < 60) return 'just now';
    const m = Math.floor(s / 60); if (m < 60) return m + 'm ago';
    const h = Math.floor(m / 60); if (h < 24) return h + 'h ago';
    const d = Math.floor(h / 24); if (d < 7) return d + 'd ago';
    try { return new Date(ms).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }); }
    catch (e) { return ''; }
}

// ── main fetch ─────────────────────────────────────────────────────────────
async function fetchFilings(force) {
    const now = Date.now();
    if (!force && _filData && (now - _filLastFetch) < _FIL_THROTTLE_MS) return;
    if (_filLoading) return;
    _filLoading = true;
    try {
        // Fetch the full set once (limit high); filtering happens client-side so
        // switching pills is instant and counts stay accurate.
        const res = await fetch('/api/filings?limit=120');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        _filData = data;
        _filLastFetch = Date.now();
        _filRender(data);
    } catch (err) {
        _filRenderError(err);
    } finally {
        _filLoading = false;
    }
}

function _filRender(d) {
    _filRenderMeta(d);
    _filRenderFilters(d);
    _filRenderFeed(d);
}

// ── hero meta (count + freshness) ──────────────────────────────────────────
function _filRenderMeta(d) {
    const el = document.getElementById('fil-meta');
    if (!el) return;
    const total = Number(d.total || (d.filings || []).length || 0);
    if (!total) { el.innerHTML = ''; return; }
    const when = _filAgo(d.as_of_ms);
    el.innerHTML =
        `<div class="fil-meta-num">${total}</div>` +
        `<div class="fil-meta-lbl">live alerts</div>` +
        (when ? `<div class="fil-meta-when">updated ${escapeHtml(when)}</div>` : '');
}

// ── filter pills ───────────────────────────────────────────────────────────
function _filRenderFilters(d) {
    const wrap = document.getElementById('fil-filter');
    if (!wrap) return;
    const types = (d.types || []).filter(t => t.count > 0);
    const total = Number(d.total || 0);
    if (!total) { wrap.innerHTML = ''; return; }

    let html = `<button class="fil-pill ${_filActiveType === 'all' ? 'active' : ''}" `
        + `onclick="setFilingFilter('all')">All <span class="fil-pill-n">${total}</span></button>`;
    types.forEach(t => {
        html += `<button class="fil-pill ${_filActiveType === t.key ? 'active' : ''}" `
            + `onclick="setFilingFilter('${t.key}')">${_filIcon(t.key)}${escapeHtml(t.label)} `
            + `<span class="fil-pill-n">${t.count}</span></button>`;
    });
    wrap.innerHTML = html;
}

function setFilingFilter(type) {
    _filActiveType = type || 'all';
    if (_filData) { _filRenderFilters(_filData); _filRenderFeed(_filData); }
}

// ── feed ───────────────────────────────────────────────────────────────────
function _filRenderFeed(d) {
    const feed = document.getElementById('fil-feed');
    if (!feed) return;
    let items = (d.filings || []).slice();
    if (_filActiveType !== 'all') items = items.filter(f => f.type === _filActiveType);

    if (!items.length) {
        _filRendered = [];
        const both = (d.degraded || {}).bse && (d.degraded || {}).news;
        feed.innerHTML = _filEmpty(d.total ? 'filtered' : (both ? 'down' : 'empty'));
        return;
    }
    _filRendered = items;
    feed.innerHTML = items.map((f, i) => _filCard(f, i)).join('');
}

function _filCard(f, i) {
    const imp = _filImpactMeta(f.impact);
    const co = escapeHtml(f.company || f.ticker_base || '—');
    const tick = f.ticker_base ? `<span class="fil-ticker">${escapeHtml(f.ticker_base)}</span>` : '';
    const detail = f.detail
        ? `<span class="fil-detail">${escapeHtml(f.detail)}</span>` : '';
    const sev = f.severity === 'high'
        ? `<span class="fil-sev sev-high"><span class="fil-sev-dot"></span>High impact</span>` : '';
    const srcCls = f.source_type === 'filing' ? 'src-filing' : 'src-news';
    // The source link must NOT bubble up to the card's "open details" handler.
    const link = f.url
        ? `<a class="fil-src-link" href="${escapeHtml(f.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">`
          + `${f.source_type === 'filing' ? 'View filing' : 'Read more'} `
          + `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7M9 7h8v8"/></svg></a>`
        : '';

    return `<article class="fil-card ${imp.cls}" onclick="openFilingDetail(${i})" role="button" tabindex="0" aria-label="Open: why this matters">
        <div class="fil-card-bar"></div>
        <div class="fil-card-main">
            <div class="fil-card-top">
                <span class="fil-type">${_filIcon(f.type)}${escapeHtml(f.type_label || '')}</span>
                <span class="fil-impact ${imp.cls}">${imp.label}</span>
                ${sev}
                <span class="fil-when">${escapeHtml(_filAgo(f.ts_ms))}</span>
            </div>
            <div class="fil-co-row">
                <span class="fil-co">${co}</span>${tick}
            </div>
            <h3 class="fil-headline">${escapeHtml(f.headline || '')}</h3>
            <p class="fil-explain">${escapeHtml(f.explanation || '')}</p>
            <div class="fil-foot">
                ${detail}
                <span class="fil-src ${srcCls}">${escapeHtml(f.source || '')}</span>
                <span class="fil-why">Why it matters
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></span>
                ${link}
            </div>
        </div>
    </article>`;
}

// ── empty / error states ────────────────────────────────────────────────────
function _filStateShell(icon, title, sub) {
    return `<div class="fil-state">
        <div class="fil-state-ico">${icon}</div>
        <div class="fil-state-title">${escapeHtml(title)}</div>
        <div class="fil-state-sub">${escapeHtml(sub)}</div>
    </div>`;
}
function _filEmpty(kind) {
    if (kind === 'filtered') {
        return _filStateShell(
            '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 4h18M6 8h12M9 12h6M11 16h2"/></svg>',
            'No filings of this type', 'Pick another category or tap "All".');
    }
    if (kind === 'down') {
        return _filStateShell(
            '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>',
            'Filing feed temporarily unavailable', 'The exchange data source is unreachable right now — it retries automatically.');
    }
    return _filStateShell(
        '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
        'No material filings right now', 'New promoter pledges, insider trades, rating changes and corporate actions will appear here as companies report them.');
}
function _filRenderError(err) {
    const feed = document.getElementById('fil-feed');
    if (feed) {
        feed.innerHTML = _filStateShell(
            '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>',
            'Couldn’t reach the filings feed', 'Retrying shortly — check your connection.');
    }
    const flt = document.getElementById('fil-filter');
    if (flt) flt.innerHTML = '';
    const meta = document.getElementById('fil-meta');
    if (meta) meta.innerHTML = '';
}

/* ===========================================================================
 * DETAIL MODAL — "why this matters" (deterministic cause→effect, no LLM)
 *
 * Clicking any alert opens this: the plain-English meaning, the cause→effect
 * MECHANISM (how the event actually moves the stock), a "what to watch next"
 * checklist, the source filing, and an honesty disclaimer. The per-type deep
 * content rides in /api/filings → `explainers`, so no extra request is needed.
 * ======================================================================== */
function _filEnsureModal() {
    let m = document.getElementById('fil-modal');
    if (m) return m;
    m = document.createElement('div');
    m.id = 'fil-modal';
    m.className = 'fil-modal hidden';
    m.setAttribute('aria-hidden', 'true');
    m.innerHTML =
        '<div class="fil-modal-backdrop" onclick="closeFilingDetail()"></div>'
        + '<div class="fil-modal-panel" role="dialog" aria-modal="true" aria-label="Filing detail">'
        + '<button class="fil-modal-close" onclick="closeFilingDetail()" aria-label="Close">'
        + '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>'
        + '<div id="fil-modal-body"></div></div>';
    document.body.appendChild(m);
    return m;
}

function openFilingDetail(i) {
    const f = _filRendered[i];
    if (!f) return;
    const deep = ((_filData && _filData.explainers) || {})[f.type] || {};
    const disclaimer = (_filData && _filData.disclaimer) || '';
    const imp = _filImpactMeta(f.impact);
    const co = escapeHtml(f.company || f.ticker_base || '—');
    const tick = f.ticker_base ? `<span class="fil-ticker">${escapeHtml(f.ticker_base)}</span>` : '';
    const sev = f.severity === 'high'
        ? '<span class="fil-sev sev-high"><span class="fil-sev-dot"></span>High impact</span>' : '';
    const when = escapeHtml(_filAgo(f.ts_ms));
    const detail = f.detail
        ? `<div class="film-detail"><span class="film-detail-lbl">Key figure</span><span class="film-detail-val">${escapeHtml(f.detail)}</span></div>` : '';
    const watch = (deep.watch || []).map(w => `<li>${escapeHtml(w)}</li>`).join('');
    const link = f.url
        ? `<a class="film-src-btn" href="${escapeHtml(f.url)}" target="_blank" rel="noopener">`
          + `${f.source_type === 'filing' ? 'View source filing' : 'Read the news'} `
          + '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7M9 7h8v8"/></svg></a>'
        : '';

    _filEnsureModal();
    document.getElementById('fil-modal-body').innerHTML = `
        <div class="film-head ${imp.cls}">
            <div class="film-head-top">
                <span class="fil-type">${_filIcon(f.type)}${escapeHtml(f.type_label || '')}</span>
                <span class="fil-impact ${imp.cls}">${imp.label} for the stock</span>
                ${sev}
                ${when ? `<span class="fil-when">${when}</span>` : ''}
            </div>
            <div class="film-co">${co}${tick}</div>
            <h2 class="film-headline">${escapeHtml(f.headline || '')}</h2>
        </div>
        <div class="film-body">
            <p class="film-lead">${escapeHtml(f.explanation || '')}</p>
            ${detail}
            ${deep.mechanism ? `<div class="film-sec"><div class="film-sec-h">How it works &amp; why it matters</div><p class="film-sec-p">${escapeHtml(deep.mechanism)}</p></div>` : ''}
            ${watch ? `<div class="film-sec"><div class="film-sec-h">What to watch next</div><ul class="film-watch">${watch}</ul></div>` : ''}
            ${deep.caveat ? `<div class="film-caveat"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01"/><circle cx="12" cy="12" r="9"/></svg><span>${escapeHtml(deep.caveat)}</span></div>` : ''}
            <div class="film-foot">${link}</div>
            ${disclaimer ? `<p class="film-disclaimer">${escapeHtml(disclaimer)}</p>` : ''}
        </div>`;

    const m = _filEnsureModal();
    m.classList.remove('hidden');
    m.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
}

function closeFilingDetail() {
    const m = document.getElementById('fil-modal');
    if (!m) return;
    m.classList.add('hidden');
    m.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
}

// Keyboard: Esc closes the modal; Enter/Space opens a focused card.
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const m = document.getElementById('fil-modal');
        if (m && !m.classList.contains('hidden')) { closeFilingDetail(); return; }
    }
    if ((e.key === 'Enter' || e.key === ' ')) {
        const card = document.activeElement;
        if (card && card.classList && card.classList.contains('fil-card')) {
            e.preventDefault();
            card.click();
        }
    }
});

/* ===========================================================================
 * AUTO-POLL while the Filings tab is open
 *
 * switchTab('filings') already does the first fetch. This adds a
 * visibility-aware refresh so new alerts appear without a manual reload, paused
 * when the tab is hidden. Wraps window.switchTab (order-independent chaining).
 * ======================================================================== */
const _FIL_POLL_MS = 180000;   // 3 min — server cache + worker absorb it
let _filPollTimer = null;

function _filStartPolling() {
    if (_filPollTimer) return;
    _filPollTimer = setInterval(() => { if (!document.hidden) fetchFilings(); }, _FIL_POLL_MS);
}
function _filStopPolling() {
    if (_filPollTimer) { clearInterval(_filPollTimer); _filPollTimer = null; }
}
(function _filHookTabLifecycle() {
    const _origSwitchTabFil = window.switchTab;
    if (typeof _origSwitchTabFil !== 'function') return;
    window.switchTab = function (tab) {
        _origSwitchTabFil.apply(this, arguments);
        if (tab === 'filings') _filStartPolling();
        else _filStopPolling();
    };
})();
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && _filPollTimer) fetchFilings();
});
