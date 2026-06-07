/* ===========================================================================
 * app-fno.js  (chunk 10/10)  —  F&O SMART MONEY
 *
 * Renders the F&O Smart-Money board: institutional positioning decoded from the
 * daily NSE derivatives bhavcopy. Market-wide bias, the four OI×price buildup
 * quadrants, unusual OI surges, delivery conviction, the index option matrix
 * (PCR / max-pain / OI walls), sector clustering, bulk/block deals, and a
 * per-stock option-chain drill-down modal.
 *
 * Data: GET /api/fno/smart-money?tickers=...  +  GET /api/fno/option-chain/<sym>
 * Both are deterministic (no LLM). Lazy-loaded by switchTab('fno').
 * Classic script — shares the global scope with the other app-*.js chunks.
 * ======================================================================== */

let _fnoData = null;
let _fnoLastFetch = 0;
let _fnoLoading = false;
const _FNO_THROTTLE_MS = 60000;   // client throttle over the server cache

function _fnoWatchlistTickers() {
    // `watchlist` is a global from app-stocks.js: [{ticker, name}, ...].
    try {
        if (Array.isArray(window.watchlist)) {
            return window.watchlist.map(w => (w && (w.ticker || w.symbol)) || '').filter(Boolean);
        }
        const raw = JSON.parse(localStorage.getItem('alpha_lens_watchlist') || '[]');
        return raw.map(w => (w && (w.ticker || w.symbol)) || w).filter(Boolean);
    } catch (e) { return []; }
}

// ── formatters ────────────────────────────────────────────────────────────
function _fnoOI(n) {
    n = Number(n || 0);
    const a = Math.abs(n);
    if (a >= 1e7) return (n / 1e7).toFixed(2) + ' Cr';
    if (a >= 1e5) return (n / 1e5).toFixed(2) + ' L';
    if (a >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return String(Math.round(n));
}
function _fnoNumF(n, d = 0) {
    const v = Number(n);
    if (!isFinite(v)) return '—';
    return v.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
}
function _fnoMove(pct, digits = 2) {
    const v = Number(pct || 0);
    const up = v >= 0;
    const arrow = up
        ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 14l6-6 6 6"/></svg>'
        : '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 10l6 6 6-6"/></svg>';
    return `<span class="fno-move ${up ? 'bull' : 'bear'}">${arrow}${up ? '+' : ''}${v.toFixed(digits)}%</span>`;
}
function _fnoDirClass(dir) {
    return dir === 'bullish' ? 'bull' : dir === 'bearish' ? 'bear' : 'flat';
}
function _fnoBiasColor(label) {
    return label === 'BULLISH' ? 'var(--green)' : label === 'BEARISH' ? 'var(--red)' : 'var(--amber)';
}
function _fnoConvBar(conv, dir) {
    const c = Math.max(0, Math.min(99, Number(conv || 0)));
    return `<div class="fno-conv"><div class="fno-conv-fill ${_fnoDirClass(dir)}" style="width:${c}%"></div><span class="fno-conv-num">${c}</span></div>`;
}
function _fnoSentChip(s) {
    const cls = s === 'BULLISH' ? 'bull' : s === 'BEARISH' ? 'bear' : 'flat';
    return `<span class="fno-chip ${cls}">${escapeHtml(s || 'NEUTRAL')}</span>`;
}
function _fnoStar(on) {
    return on
        ? '<svg class="fno-star" width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3 7h7l-5.5 4 2 7L12 16l-6.5 4 2-7L2 9h7z"/></svg>'
        : '';
}

// ── main fetch ──────────────────────────────────────────────────────────
async function fetchFnoSmartMoney(force) {
    const now = Date.now();
    if (!force && _fnoData && (now - _fnoLastFetch) < _FNO_THROTTLE_MS) return;
    if (_fnoLoading) return;
    _fnoLoading = true;
    try {
        const tickers = _fnoWatchlistTickers();
        const q = tickers.length ? `?tickers=${encodeURIComponent(tickers.join(','))}` : '';
        const res = await fetch(`/api/fno/smart-money${q}`);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        _fnoData = data;
        _fnoLastFetch = Date.now();
        _renderFno(data);
    } catch (err) {
        _fnoRenderError(err);
    } finally {
        _fnoLoading = false;
    }
}

function _renderFno(d) {
    if (!d || d.applicable === false || !d.universe_count) { _fnoRenderEmpty(d); return; }
    _fnoRenderBias(d);
    _fnoRenderStats(d);
    _fnoRenderMeta(d);
    _fnoRenderNarrative(d);
    _fnoRenderIndexMatrix(d.index_matrix || []);
    _fnoRenderQuadrants(d.buildups || {});
    _fnoRenderUnusual(d.unusual_oi || []);
    _fnoRenderDelivery(d.delivery_spikes || [], (d.degraded || {}).delivery);
    _fnoRenderSectors(d.sectors || []);
    _fnoRenderDeals(d.deals || [], (d.degraded || {}).deals);
}

// ── hero: bias gauge + stats + meta ───────────────────────────────────────
function _fnoRenderBias(d) {
    const b = d.market_bias || { score: 0, label: 'NEUTRAL' };
    const valEl = document.getElementById('fno-bias-value');
    const fillEl = document.getElementById('fno-bias-fill');
    const subEl = document.getElementById('fno-bias-sub');
    const color = _fnoBiasColor(b.label);
    if (valEl) { valEl.textContent = b.label; valEl.style.color = color; }
    if (fillEl) {
        const pct = Math.max(2, Math.min(98, (Number(b.score || 0) + 100) / 2));
        fillEl.style.width = pct + '%';
        fillEl.style.background = color;
    }
    if (subEl) {
        subEl.innerHTML = `Bias score <strong style="color:${color}">${Number(b.score || 0) >= 0 ? '+' : ''}${Number(b.score || 0).toFixed(0)}</strong> `
            + `· ${_fnoNumF(b.bull_pressure)} bull / ${_fnoNumF(b.bear_pressure)} bear pressure`;
    }
}
function _fnoRenderStats(d) {
    const c = d.counts || {};
    const cells = [
        [c['Long Buildup'] || 0, 'Long Buildup', 'bull'],
        [c['Short Buildup'] || 0, 'Short Buildup', 'bear'],
        [(d.unusual_oi || []).length, 'Unusual OI', 'flat'],
        [d.universe_count || 0, 'F&O Universe', 'flat'],
    ];
    const el = document.getElementById('fno-stats');
    if (!el) return;
    el.innerHTML = cells.map((x, i) =>
        `${i ? '<div class="fno-stat-divider"></div>' : ''}<div class="fno-stat-cell"><div class="fno-stat-value ${x[2]}">${_fnoNumF(x[0])}</div><div class="fno-stat-label">${x[1]}</div></div>`
    ).join('');
}
function _fnoRenderMeta(d) {
    const el = document.getElementById('fno-meta');
    if (!el) return;
    const date = d.bhavcopy_date ? `Bhavcopy ${escapeHtml(d.bhavcopy_date)}` : 'Bhavcopy pending';
    const wl = (d.watchlist || []).length;
    el.innerHTML = `<span class="fno-meta-pill"><span class="pill-dot"></span>${date}</span>`
        + (wl ? `<span class="fno-meta-pill">${wl} in your watchlist</span>` : '');
}
function _fnoRenderNarrative(d) {
    const el = document.getElementById('fno-narrative');
    if (!el) return;
    el.innerHTML = `<div class="fno-narr-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/><path d="M12 8v4M12 16h.01"/></svg></div>`
        + `<p class="fno-narr-text">${escapeHtml(d.narrative || '')}</p>`;
}

// ── index option matrix ───────────────────────────────────────────────────
function _fnoRenderIndexMatrix(rows) {
    const el = document.getElementById('fno-index-grid');
    if (!el) return;
    if (!rows.length) {
        el.innerHTML = _fnoMini('No index option data in the latest bhavcopy.');
        document.getElementById('fno-index-section').style.display = '';
        return;
    }
    el.innerHTML = rows.map(r => {
        const gap = r.max_pain_gap_pct;
        const gapTxt = (gap === null || gap === undefined) ? '' :
            `<span class="fno-idx-gap ${gap >= 0 ? 'bull' : 'bear'}">${gap >= 0 ? '+' : ''}${Number(gap).toFixed(1)}% vs spot</span>`;
        const pcr = (r.pcr === null || r.pcr === undefined) ? '—' : Number(r.pcr).toFixed(2);
        const pcrCls = r.pcr >= 1.2 ? 'bull' : r.pcr <= 0.8 ? 'bear' : 'flat';
        return `<button type="button" class="fno-idx-card" onclick="openFnoOptionChain('${escapeHtml(r.symbol)}')">
            <div class="fno-idx-head"><span class="fno-idx-name">${escapeHtml(r.label || r.symbol)}</span>${_fnoSentChip(r.sentiment)}</div>
            <div class="fno-idx-spot">${r.spot ? _fnoNumF(r.spot, 0) : '—'}</div>
            <div class="fno-idx-pcr"><span class="fno-idx-pcr-num ${pcrCls}">${pcr}</span><span class="fno-idx-pcr-lbl">PCR</span></div>
            <div class="fno-idx-rows">
                <div class="fno-idx-row"><span>Max Pain</span><strong>${r.max_pain ? _fnoNumF(r.max_pain, 0) : '—'}</strong></div>
                ${gapTxt ? `<div class="fno-idx-row"><span></span>${gapTxt}</div>` : ''}
                <div class="fno-idx-row"><span>Call Wall (R)</span><strong class="bear">${r.call_wall ? _fnoNumF(r.call_wall, 0) : '—'}</strong></div>
                <div class="fno-idx-row"><span>Put Wall (S)</span><strong class="bull">${r.put_wall ? _fnoNumF(r.put_wall, 0) : '—'}</strong></div>
            </div>
        </button>`;
    }).join('');
}

// ── smart-money quadrants ─────────────────────────────────────────────────
const _FNO_QUADS = [
    ['LONG_BUILDUP', 'Long Buildup', 'bull', 'Fresh longs · price ↑ OI ↑'],
    ['SHORT_BUILDUP', 'Short Buildup', 'bear', 'Fresh shorts · price ↓ OI ↑'],
    ['SHORT_COVERING', 'Short Covering', 'bull', 'Shorts exiting · price ↑ OI ↓'],
    ['LONG_UNWINDING', 'Long Unwinding', 'bear', 'Longs exiting · price ↓ OI ↓'],
];
function _fnoRowTable(rows) {
    if (!rows.length) return `<div class="fno-quad-empty">No names in this bucket today.</div>`;
    return `<table class="fno-table"><tbody>` + rows.map(r => `
        <tr onclick="openFnoOptionChain('${escapeHtml(r.symbol)}')">
            <td class="fno-td-sym">${_fnoStar(r.in_watchlist)}<span class="fno-sym">${escapeHtml(r.symbol)}</span><span class="fno-sec">${escapeHtml(r.sector)}</span></td>
            <td class="fno-td-num" data-label="Price">${_fnoMove(r.px_chg_pct)}</td>
            <td class="fno-td-num" data-label="OI Δ">${_fnoMove(r.oi_chg_pct)}</td>
            <td class="fno-td-conv" data-label="Conviction">${_fnoConvBar(r.conviction, r.direction)}</td>
        </tr>`).join('') + `</tbody></table>`;
}
function _fnoRenderQuadrants(buildups) {
    const el = document.getElementById('fno-quadrants');
    if (!el) return;
    el.innerHTML = _FNO_QUADS.map(([key, label, cls, hint]) => {
        const rows = buildups[key] || [];
        return `<div class="fno-quad fno-quad-${cls}">
            <div class="fno-quad-head">
                <div><div class="fno-quad-title">${label}</div><div class="fno-quad-hint">${hint}</div></div>
                <span class="fno-quad-count ${cls}">${rows.length}</span>
            </div>
            ${_fnoRowTable(rows)}
        </div>`;
    }).join('');
}

// ── unusual OI ─────────────────────────────────────────────────────────────
function _fnoRenderUnusual(rows) {
    const el = document.getElementById('fno-unusual');
    if (!el) return;
    if (!rows.length) { el.innerHTML = _fnoMini('No unusual OI surges today.'); return; }
    el.innerHTML = `<div class="fno-list">` + rows.map(r => `
        <div class="fno-list-row" onclick="openFnoOptionChain('${escapeHtml(r.symbol)}')">
            <div class="fno-list-main"><span class="fno-sym">${escapeHtml(r.symbol)}</span><span class="fno-chip ${_fnoDirClass(r.direction)}">${escapeHtml(r.buildup_label)}</span></div>
            <div class="fno-list-stat"><span class="fno-big ${_fnoDirClass(r.direction)}">${r.oi_chg_pct >= 0 ? '+' : ''}${Number(r.oi_chg_pct).toFixed(0)}%</span><span class="fno-small">OI · ${_fnoMove(r.px_chg_pct)}</span></div>
        </div>`).join('') + `</div>`;
}

// ── delivery conviction ────────────────────────────────────────────────────
function _fnoRenderDelivery(rows, degraded) {
    const el = document.getElementById('fno-delivery');
    if (!el) return;
    if (degraded) { el.innerHTML = _fnoMini('Delivery data unavailable from the source today.'); return; }
    if (!rows.length) { el.innerHTML = _fnoMini('No high-delivery accumulation flagged today.'); return; }
    el.innerHTML = `<div class="fno-list">` + rows.map(r => `
        <div class="fno-list-row" onclick="openFnoOptionChain('${escapeHtml(r.symbol)}')">
            <div class="fno-list-main"><span class="fno-sym">${escapeHtml(r.symbol)}</span><span class="fno-chip ${_fnoDirClass(r.direction)}">${escapeHtml(r.buildup_label)}</span></div>
            <div class="fno-deliv"><div class="fno-deliv-bar"><div class="fno-deliv-fill" style="width:${Math.min(100, Number(r.delivery_pct || 0))}%"></div></div><span class="fno-deliv-num">${Number(r.delivery_pct).toFixed(0)}%</span></div>
        </div>`).join('') + `</div>`;
}

// ── sector clustering ──────────────────────────────────────────────────────
function _fnoRenderSectors(rows) {
    const el = document.getElementById('fno-sectors');
    if (!el) return;
    if (!rows.length) { el.innerHTML = _fnoMini('No sector-level clustering detected.'); return; }
    el.innerHTML = `<div class="fno-sectors">` + rows.map(r => {
        const net = Number(r.net_bias || 0);
        const w = Math.min(50, Math.abs(net) / 2);   // half-bar, 0..50%
        const cls = net > 15 ? 'bull' : net < -15 ? 'bear' : 'flat';
        return `<div class="fno-sec-row">
            <div class="fno-sec-name">${escapeHtml(r.sector)}<span class="fno-sec-count">${r.count}</span></div>
            <div class="fno-sec-track">
                <div class="fno-sec-bar ${cls}" style="width:${w}%;${net >= 0 ? 'left:50%' : 'right:50%'}"></div>
                <div class="fno-sec-axis"></div>
            </div>
            <div class="fno-sec-val ${cls}">${net >= 0 ? '+' : ''}${net.toFixed(0)}</div>
        </div>`;
    }).join('') + `</div>`;
}

// ── bulk / block deals ─────────────────────────────────────────────────────
function _fnoRenderDeals(rows, degraded) {
    const el = document.getElementById('fno-deals');
    if (!el) return;
    if (degraded || !rows.length) {
        el.innerHTML = _fnoMini(degraded ? 'Bulk/block deal feed unavailable from the source today.' : 'No bulk or block deals reported in the latest session.');
        return;
    }
    el.innerHTML = `<table class="fno-table fno-deals-table"><thead><tr>
            <th>Stock</th><th>Side</th><th>Client</th><th class="fno-num">Qty</th><th class="fno-num">Price</th><th>Type</th></tr></thead><tbody>`
        + rows.map(r => `<tr>
            <td class="fno-td-sym"><span class="fno-sym">${escapeHtml(r.symbol)}</span></td>
            <td data-label="Side"><span class="fno-chip ${r.side === 'BUY' ? 'bull' : r.side === 'SELL' ? 'bear' : 'flat'}">${escapeHtml(r.side || '—')}</span></td>
            <td class="fno-td-client" data-label="Client">${escapeHtml(r.client || '—')}</td>
            <td class="fno-num" data-label="Qty">${escapeHtml(r.qty || '—')}</td>
            <td class="fno-num" data-label="Price">${escapeHtml(r.price || '—')}</td>
            <td data-label="Type"><span class="fno-chip flat">${escapeHtml((r.kind || '').toUpperCase())}</span></td>
        </tr>`).join('') + `</tbody></table>`;
}

// ── shared tiny states ─────────────────────────────────────────────────────
function _fnoMini(msg) {
    return `<div class="fno-mini">${escapeHtml(msg)}</div>`;
}
function _fnoRenderEmpty(d) {
    const grid = document.getElementById('fno-index-grid');
    const quad = document.getElementById('fno-quadrants');
    const narr = document.getElementById('fno-narrative');
    const degraded = (d && d.degraded) || {};
    const why = degraded.futures
        ? 'The NSE F&O bhavcopy could not be reached right now. It publishes ~7-8 PM IST each trading day — this view fills in once it is available.'
        : 'No F&O positioning to show yet. Check back after the market session and the evening bhavcopy publish.';
    const shell = `<div class="fno-empty">
        <div class="fno-empty-icon"><svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/></svg></div>
        <div class="fno-empty-title">No F&amp;O data right now</div>
        <p class="fno-empty-sub">${why}</p></div>`;
    if (narr) narr.innerHTML = shell;
    if (grid) grid.innerHTML = '';
    if (quad) quad.innerHTML = '';
    ['fno-unusual', 'fno-delivery', 'fno-sectors', 'fno-deals'].forEach(id => {
        const e = document.getElementById(id); if (e) e.innerHTML = _fnoMini('—');
    });
    const biasVal = document.getElementById('fno-bias-value');
    if (biasVal) { biasVal.textContent = 'NO DATA'; biasVal.style.color = 'var(--text-3, #8a8a99)'; }
}
function _fnoRenderError(err) {
    const narr = document.getElementById('fno-narrative');
    if (narr) narr.innerHTML = `<div class="fno-empty">
        <div class="fno-empty-icon err"><svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg></div>
        <div class="fno-empty-title">Couldn’t reach the F&amp;O engine</div>
        <p class="fno-empty-sub">${escapeHtml(String(err && err.message ? err.message : err))} — retrying on the next visit.</p></div>`;
    const biasVal = document.getElementById('fno-bias-value');
    if (biasVal) { biasVal.textContent = 'OFFLINE'; biasVal.style.color = 'var(--red)'; }
}

/* ===========================================================================
 * OPTION-CHAIN DRILL-DOWN MODAL
 * ======================================================================== */
async function openFnoOptionChain(symbol) {
    const modal = document.getElementById('fno-modal');
    const body = document.getElementById('fno-modal-body');
    if (!modal || !body) return;
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    body.innerHTML = `<div class="fno-modal-loading"><div class="fno-spinner"></div><span>Loading ${escapeHtml(symbol)} option chain…</span></div>`;
    try {
        const res = await fetch(`/api/fno/option-chain/${encodeURIComponent(symbol)}`);
        if (res.status === 404) {
            body.innerHTML = `<div class="fno-empty"><div class="fno-empty-title">No option chain</div><p class="fno-empty-sub">${escapeHtml(symbol)} has no F&amp;O options in the latest bhavcopy.</p></div>`;
            return;
        }
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        _renderFnoOptionChain(data);
    } catch (err) {
        body.innerHTML = `<div class="fno-empty"><div class="fno-empty-title">Couldn’t load chain</div><p class="fno-empty-sub">${escapeHtml(String(err && err.message ? err.message : err))}</p></div>`;
    }
}

function closeFnoModal() {
    const modal = document.getElementById('fno-modal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
}

function _renderFnoOptionChain(d) {
    const body = document.getElementById('fno-modal-body');
    if (!body) return;
    const ladder = d.ladder || [];
    const spot = Number(d.spot || 0);
    // ATM = strike closest to spot
    let atm = null, atmGap = Infinity;
    ladder.forEach(s => { const g = Math.abs(Number(s.strike) - spot); if (g < atmGap) { atmGap = g; atm = s.strike; } });
    const maxOI = Math.max(1, ...ladder.map(s => Math.max(Number(s.ce_oi || 0), Number(s.pe_oi || 0))));
    const pcr = (d.pcr === null || d.pcr === undefined) ? '—' : Number(d.pcr).toFixed(2);
    const pcrCls = d.pcr >= 1.2 ? 'bull' : d.pcr <= 0.8 ? 'bear' : 'flat';
    const gap = d.max_pain_gap_pct;

    const stats = [
        [`<span class="${pcrCls}">${pcr}</span>`, 'PCR (OI)'],
        [d.max_pain ? _fnoNumF(d.max_pain, 0) : '—', 'Max Pain'],
        [d.call_wall ? `<span class="bear">${_fnoNumF(d.call_wall, 0)}</span>` : '—', 'Call Wall (R)'],
        [d.put_wall ? `<span class="bull">${_fnoNumF(d.put_wall, 0)}</span>` : '—', 'Put Wall (S)'],
    ];

    const rowsHtml = ladder.map(s => {
        const ceW = Math.min(100, Number(s.ce_oi || 0) / maxOI * 100);
        const peW = Math.min(100, Number(s.pe_oi || 0) / maxOI * 100);
        const isAtm = s.strike === atm;
        const isCW = s.strike === d.call_wall;
        const isPW = s.strike === d.put_wall;
        return `<tr class="${isAtm ? 'fno-oc-atm' : ''}">
            <td class="fno-oc-ce">
                <div class="fno-oc-bar-wrap"><div class="fno-oc-bar ce" style="width:${ceW}%"></div></div>
                <span class="fno-oc-oi">${_fnoOI(s.ce_oi)}</span>
                <span class="fno-oc-chg ${Number(s.ce_chg) >= 0 ? 'bear' : 'bull'}">${Number(s.ce_chg) >= 0 ? '+' : ''}${_fnoOI(s.ce_chg)}</span>
            </td>
            <td class="fno-oc-strike">${_fnoNumF(s.strike, 0)}${isCW ? '<span class="fno-oc-tag r">R</span>' : ''}${isPW ? '<span class="fno-oc-tag s">S</span>' : ''}</td>
            <td class="fno-oc-pe">
                <span class="fno-oc-chg ${Number(s.pe_chg) >= 0 ? 'bull' : 'bear'}">${Number(s.pe_chg) >= 0 ? '+' : ''}${_fnoOI(s.pe_chg)}</span>
                <span class="fno-oc-oi">${_fnoOI(s.pe_oi)}</span>
                <div class="fno-oc-bar-wrap"><div class="fno-oc-bar pe" style="width:${peW}%"></div></div>
            </td>
        </tr>`;
    }).join('');

    body.innerHTML = `
        <div class="fno-oc-head">
            <div>
                <div class="fno-oc-title">${escapeHtml(d.symbol)} ${d.is_index ? '<span class="fno-chip flat">INDEX</span>' : ''}</div>
                <div class="fno-oc-sub">Expiry ${escapeHtml(d.expiry || '—')} · Spot ${spot ? _fnoNumF(spot, 2) : '—'}</div>
            </div>
            ${_fnoSentChip(d.sentiment)}
        </div>
        <div class="fno-oc-stats">${stats.map(s => `<div class="fno-oc-stat"><div class="fno-oc-stat-v">${s[0]}</div><div class="fno-oc-stat-l">${s[1]}</div></div>`).join('')}
            ${(gap !== null && gap !== undefined) ? `<div class="fno-oc-stat"><div class="fno-oc-stat-v ${gap >= 0 ? 'bull' : 'bear'}">${gap >= 0 ? '+' : ''}${Number(gap).toFixed(1)}%</div><div class="fno-oc-stat-l">Spot vs Pain</div></div>` : ''}
        </div>
        <div class="fno-oc-legend"><span><i class="dot ce"></i>Calls (CE)</span><span>Strike</span><span><i class="dot pe"></i>Puts (PE)</span></div>
        <div class="fno-oc-table-wrap">
            <table class="fno-oc-table"><thead><tr><th>Call OI / Δ</th><th>Strike</th><th>Put OI / Δ</th></tr></thead>
            <tbody>${rowsHtml || '<tr><td colspan="3" class="fno-oc-empty">No strikes in the chain.</td></tr>'}</tbody></table>
        </div>`;
}

// Close modal on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const m = document.getElementById('fno-modal');
        if (m && !m.classList.contains('hidden')) closeFnoModal();
    }
});
