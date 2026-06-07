function _rippleColorForDirection(dir) {
    return (dir || '').toUpperCase() === 'BULLISH' ? '#10b981' : '#f43f5e';
}
function _rippleBgForDirection(dir) {
    return (dir || '').toUpperCase() === 'BULLISH'
        ? 'rgba(16,185,129,0.12)'
        : 'rgba(244,63,94,0.12)';
}
function _rippleBorderForDirection(dir) {
    return (dir || '').toUpperCase() === 'BULLISH'
        ? 'rgba(16,185,129,0.35)'
        : 'rgba(244,63,94,0.35)';
}

let _rippleActiveNode = null;

function _renderRippleSidePanel(node, container) {
    _rippleActiveNode = node;
    // Reset all chip highlights
    document.querySelectorAll('.rfl-chip').forEach(el => el.classList.remove('rfl-chip--active'));
    if (node) {
        const el = document.getElementById(`rfl-chip-${node._uid}`);
        if (el) el.classList.add('rfl-chip--active');
    }
    if (!node) {
        container.innerHTML = `
            <div class="ripple-side-empty">
                <div class="ripple-side-empty-icon"><svg viewBox="0 0 24 24" width="34" height="34" fill="currentColor"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg></div>
                <div class="ripple-side-empty-text">Click any stock chip to see its causal chain &amp; reasoning</div>
            </div>`;
        return;
    }
    const dir = (node.direction || '').toUpperCase();
    const dirCls = dir === 'BULLISH' ? 'bullish' : 'bearish';
    const tierLabels = {1: 'Tier 1 · Direct Impact', 2: 'Tier 2 · Supply Chain', 3: 'Tier 3 · Macro Transmission'};
    container.innerHTML = `
        <div class="ripple-side-card">
            <div class="ripple-side-tier-label">${tierLabels[node.tier] || ''}</div>
            <div class="ripple-side-ticker">${escapeHtml(node.ticker || '')}</div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <span class="ripple-side-direction ${dirCls}">
                    ${dir === 'BULLISH'
                        ? '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 14l6-6 6 6"/></svg>'
                        : '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 10l6 6 6-6"/></svg>'
                    }
                    ${dir || 'NEUTRAL'}
                </span>
                <span class="ripple-side-conf">Confidence ${node.confidence != null ? node.confidence : '—'}%</span>
            </div>
            <div class="ripple-side-reason">${escapeHtml(node.reason || 'No detailed reason provided.')}</div>
        </div>`;
}

async function _renderRippleGraph(payload) {
    const wrap = document.getElementById('ripple-graph-wrap');
    const sideEl = document.getElementById('ripple-side');
    const loadingEl = document.getElementById('ripple-loading');
    const svgEl = document.getElementById('ripple-graph');

    if (loadingEl) loadingEl.style.display = 'none';
    if (svgEl) svgEl.style.display = 'none'; // hide the legacy SVG element

    // Build tier data
    const tiers = Array.isArray(payload.tiers) ? payload.tiers : [];
    let uidCounter = 0;
    const tierDefs = [
        { num: 1, label: 'Tier 1', sublabel: 'Direct Impact',        color: '#fbbf24', borderColor: 'rgba(251,191,36,0.30)' },
        { num: 2, label: 'Tier 2', sublabel: 'Supply Chain',         color: '#60a5fa', borderColor: 'rgba(96,165,250,0.30)' },
        { num: 3, label: 'Tier 3', sublabel: 'Macro Transmission',   color: '#a78bfa', borderColor: 'rgba(167,139,250,0.30)' },
    ];

    const resolvedTiers = tierDefs.map(td => {
        const found = tiers.find(t => t.tier === td.num);
        const nodes = (found && found.nodes) ? found.nodes.map(n => ({ ...n, tier: td.num, _uid: uidCounter++ })) : [];
        return { ...td, nodes };
    });

    // Remove any previous arrow-flow container
    const prev = wrap.querySelector('.rfl-container');
    if (prev) prev.remove();

    // Build the HTML arrow-flow layout
    const triggerLabel = escapeHtml(payload.instrument || payload.headline || 'MACRO EVENT');
    const allTiersEmpty = resolvedTiers.every(t => t.nodes.length === 0);

    if (allTiersEmpty) {
        wrap.insertAdjacentHTML('beforeend', `
            <div class="rfl-container rfl-empty-state">
                <div class="ripple-side-empty-icon"><svg viewBox="0 0 24 24" width="34" height="34" fill="currentColor"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg></div>
                <div class="ripple-side-empty-text">No propagation data available for this event yet.</div>
            </div>`);
        return;
    }

    let flowHTML = `<div class="rfl-container">`;

    // ── Trigger block ──
    flowHTML += `
        <div class="rfl-column">
            <div class="rfl-col-header">
                <span class="rfl-col-label" style="color:#c4b5fd;">TRIGGER</span>
                <span class="rfl-col-sublabel">Shock Event</span>
            </div>
            <div class="rfl-chip rfl-chip--trigger">
                <span class="rfl-chip-icon"><svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" style="vertical-align:-2px"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg></span>
                <span class="rfl-chip-ticker">${triggerLabel}</span>
            </div>
        </div>`;

    // ── Tier columns ──
    resolvedTiers.forEach((td, idx) => {
        if (td.nodes.length === 0) return;

        // Arrow separator — flows from the previous tier's color into this one.
        const fromColor = idx === 0 ? '#c4b5fd' : (tierDefs[idx-1] ? tierDefs[idx-1].color : '#c4b5fd');
        flowHTML += `
            <div class="rfl-arrow-col">
                <svg class="rfl-arrow-svg" viewBox="0 0 64 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <linearGradient id="rfl-grad-${idx}" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stop-color="${fromColor}" stop-opacity="0.85"/>
                            <stop offset="100%" stop-color="${td.color}" stop-opacity="1"/>
                        </linearGradient>
                        <marker id="rfl-arrow-${idx}" markerWidth="9" markerHeight="9" refX="5" refY="4" orient="auto">
                            <path d="M0,0 L0,8 L8,4 z" fill="${td.color}"/>
                        </marker>
                    </defs>
                    <line class="rfl-arrow-flow" x1="2" y1="9" x2="50" y2="9"
                        stroke="url(#rfl-grad-${idx})" stroke-width="3" stroke-linecap="round"
                        marker-end="url(#rfl-arrow-${idx})"
                        stroke-dasharray="6 5" />
                </svg>
                <span class="rfl-arrow-label" style="color:${td.color};">${td.nodes.length} stock${td.nodes.length !== 1 ? 's' : ''}</span>
            </div>`;

        // Tier column
        flowHTML += `
            <div class="rfl-column">
                <div class="rfl-col-header">
                    <span class="rfl-col-label" style="color:${td.color};">${td.label}</span>
                    <span class="rfl-col-sublabel">${td.sublabel}</span>
                </div>
                <div class="rfl-chips-wrap">`;

        td.nodes.forEach(n => {
            const dir = (n.direction || '').toUpperCase();
            const isBull = dir === 'BULLISH';
            const chipColor = isBull ? '#34d399' : '#fb7185';
            const chipBg = isBull ? 'rgba(16,185,129,0.10)' : 'rgba(244,63,94,0.10)';
            const chipBorder = isBull ? 'rgba(16,185,129,0.30)' : 'rgba(244,63,94,0.30)';
            const arrowIcon = isBull
                ? `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 14l6-6 6 6"/></svg>`
                : `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 10l6 6 6-6"/></svg>`;
            flowHTML += `
                <div class="rfl-chip" id="rfl-chip-${n._uid}"
                    data-uid="${n._uid}"
                    style="border-color:${chipBorder};background:${chipBg};"
                    onclick="_rflChipClick(${n._uid})">
                    <span class="rfl-chip-dir" style="color:${chipColor};">${arrowIcon}</span>
                    <span class="rfl-chip-ticker">${escapeHtml(n.ticker || '')}</span>
                    ${n.confidence != null ? `<span class="rfl-chip-conf" style="color:${td.color};">${n.confidence}%</span>` : ''}
                </div>`;
        });

        flowHTML += `</div></div>`;
    });

    flowHTML += `</div>`; // close rfl-container

    wrap.insertAdjacentHTML('beforeend', flowHTML);

    // Store node data globally for click handler
    window._rflNodeMap = {};
    resolvedTiers.forEach(td => {
        td.nodes.forEach(n => { window._rflNodeMap[n._uid] = n; });
    });

    // Reset side panel
    _renderRippleSidePanel(null, sideEl);
}

window._rflChipClick = function(uid) {
    const node = window._rflNodeMap && window._rflNodeMap[uid];
    const sideEl = document.getElementById('ripple-side');
    if (!sideEl) return;
    if (_rippleActiveNode && _rippleActiveNode._uid === uid) {
        // Deselect on second click
        _rippleActiveNode = null;
        _renderRippleSidePanel(null, sideEl);
    } else {
        _renderRippleSidePanel(node, sideEl);
    }
};

async function openRipple(newsId) {
    const modal = document.getElementById('ripple-modal');
    const headline = document.getElementById('ripple-headline');
    const summary = document.getElementById('ripple-summary');
    const loading = document.getElementById('ripple-loading');
    const svg = document.getElementById('ripple-graph');
    const side = document.getElementById('ripple-side');
    const wrap = document.getElementById('ripple-graph-wrap');

    if (!modal) return;
    headline.innerText = 'Loading…';
    summary.innerText = '';
    // Clear any previous arrow-flow
    if (wrap) { const old = wrap.querySelector('.rfl-container'); if (old) old.remove(); }
    if (loading) loading.style.display = 'flex';
    if (svg) { svg.style.display = 'none'; }
    _rippleActiveNode = null;
    if (side) {
        side.innerHTML = `
            <div class="ripple-side-empty">
                <div class="ripple-side-empty-icon"><svg viewBox="0 0 24 24" width="34" height="34" fill="currentColor"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg></div>
                <div class="ripple-side-empty-text">Click any stock chip to see its causal chain &amp; reasoning</div>
            </div>`;
    }
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';

    try {
        const res = await fetch(`/api/news/${newsId}/ripple`);
        if (!res.ok) {
            const errBody = await res.json().catch(() => ({}));
            headline.innerText = 'Could not load The Ripple';
            summary.innerText = errBody.error || `HTTP ${res.status}`;
            if (loading) loading.style.display = 'none';
            return;
        }
        const data = await res.json();
        headline.innerText = data.headline || '';
        summary.innerText = data.summary || '';
        await _renderRippleGraph(data);
    } catch (err) {
        headline.innerText = 'Could not load The Ripple';
        summary.innerText = String(err && err.message ? err.message : err);
        if (loading) loading.style.display = 'none';
    }
}

function closeRipple() {
    const modal = document.getElementById('ripple-modal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    // Clean up arrow-flow on close
    const wrap = document.getElementById('ripple-graph-wrap');
    if (wrap) { const old = wrap.querySelector('.rfl-container'); if (old) old.remove(); }
    _rippleActiveNode = null;
}

// Global click handlers for backdrop + close button (delegated so they
// survive re-renders).
document.addEventListener('click', (e) => {
    if (e.target.closest('[data-close-ripple]')) {
        closeRipple();
    }
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeRipple();
});

// Re-render the graph on window resize so the SVG fills the new wrap size.
let _rippleResizeTimer = null;
window.addEventListener('resize', () => {
    const modal = document.getElementById('ripple-modal');
    if (!modal || modal.classList.contains('hidden')) return;
    clearTimeout(_rippleResizeTimer);
    _rippleResizeTimer = setTimeout(() => {
        // Re-fit viewBox; the existing simulation positions are still valid.
        const svg = document.getElementById('ripple-graph');
        const wrap = document.getElementById('ripple-graph-wrap');
        if (svg && wrap) {
            const r = wrap.getBoundingClientRect();
            svg.setAttribute('viewBox', `0 0 ${r.width} ${r.height || 460}`);
        }
    }, 150);
});

// Expose globally for inline handlers / debugging
window.openRipple = openRipple;
window.closeRipple = closeRipple;

// ════════════════════════════════════════════════════════════════════════
// THE RIPPLE 2.0 — deterministic quantitative five-dimension cascade
// Fetches /api/macro/events/<id>/ripple2 (pure engine, no LLM) and renders:
//   Direct · Second-order · Sector · Portfolio · Action window
// Personalized portfolio dimension via the user's watchlist (?tickers=).
// ════════════════════════════════════════════════════════════════════════

function _r2WatchlistTickers() {
    // `watchlist` is a global from app-stocks.js: [{ticker, name}, ...].
    try {
        if (Array.isArray(window.watchlist)) {
            return window.watchlist.map(w => (w && (w.ticker || w.symbol)) || '').filter(Boolean);
        }
        const raw = JSON.parse(localStorage.getItem('alpha_lens_watchlist') || '[]');
        return raw.map(w => (w && (w.ticker || w.symbol)) || w).filter(Boolean);
    } catch (e) { return []; }
}

function _r2Move(pct) {
    const v = Number(pct || 0);
    const up = v >= 0;
    const arrow = up
        ? '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 14l6-6 6 6"/></svg>'
        : '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 10l6 6 6-6"/></svg>';
    return `<span class="r2-move ${up ? 'bull' : 'bear'}">${arrow}${up ? '+' : ''}${v.toFixed(2)}%</span>`;
}

function _r2StockRow(n) {
    const bull = n.direction === 'BULLISH';
    return `
        <div class="r2-row ${bull ? 'is-bull' : 'is-bear'}">
            <div class="r2-row-top">
                <div class="r2-row-id">
                    <span class="r2-tkr">${escapeHtml((n.ticker || '').replace(/\.(NS|BO)$/i, ''))}</span>
                    <span class="r2-sector">${escapeHtml(n.sector || '')}</span>
                </div>
                <div class="r2-row-metrics">
                    ${_r2Move(n.expected_move_pct)}
                    <span class="r2-conf" title="Model confidence">${n.confidence != null ? n.confidence + '%' : '—'}</span>
                </div>
            </div>
            <div class="r2-mech">${escapeHtml(n.mechanism || '')}</div>
            <div class="r2-row-foot">
                <span class="r2-lag r2-lag--${n.lag === 'lagged' ? 'lag' : 'now'}">${n.lag === 'lagged' ? 'Lagged · 1–3 sessions' : 'Immediate'}</span>
            </div>
        </div>`;
}

function _r2NodeListPanel(title, sub, nodes, accent) {
    let inner;
    if (!nodes || !nodes.length) {
        inner = `<div class="r2-panel-empty">No material ${title.toLowerCase()} names for this shock.</div>`;
    } else {
        inner = nodes.map(_r2StockRow).join('');
    }
    return `
        <div class="r2-panel" style="--r2-accent:${accent};">
            <div class="r2-panel-head">
                <div class="r2-panel-title">${title}</div>
                <div class="r2-panel-sub">${sub}</div>
                ${nodes && nodes.length ? `<span class="r2-panel-count">${nodes.length}</span>` : ''}
            </div>
            <div class="r2-panel-body">${inner}</div>
        </div>`;
}

function _r2SectorPanel(sectors) {
    let inner;
    if (!sectors || !sectors.length) {
        inner = `<div class="r2-panel-empty">No sector-level concentration detected.</div>`;
    } else {
        const maxNet = Math.max(...sectors.map(s => Math.abs(s.net_move_pct)), 0.01);
        inner = sectors.map(s => {
            const bull = s.net_move_pct >= 0;
            const w = Math.max(4, Math.round(Math.abs(s.net_move_pct) / maxNet * 50)); // % of half-width
            const tops = (s.top || []).map(t => (t.ticker || '').replace(/\.(NS|BO)$/i, '')).join(' · ');
            return `
                <div class="r2-sec">
                    <div class="r2-sec-head">
                        <span class="r2-sec-name">${escapeHtml(s.sector)}</span>
                        <span class="r2-sec-net ${bull ? 'bull' : 'bear'}">${bull ? '+' : ''}${Number(s.net_move_pct).toFixed(2)}%</span>
                    </div>
                    <div class="r2-sec-track">
                        <div class="r2-sec-mid"></div>
                        <div class="r2-sec-fill ${bull ? 'bull' : 'bear'}" style="width:${w}%;${bull ? 'left:50%;' : 'right:50%;'}"></div>
                    </div>
                    <div class="r2-sec-foot"><span class="r2-sec-count">${s.count} name${s.count !== 1 ? 's' : ''}</span><span class="r2-sec-top">${escapeHtml(tops)}</span></div>
                </div>`;
        }).join('');
    }
    return `
        <div class="r2-panel" style="--r2-accent:var(--accent);">
            <div class="r2-panel-head">
                <div class="r2-panel-title">Sector Impact</div>
                <div class="r2-panel-sub">Net directional bias by sector</div>
            </div>
            <div class="r2-panel-body">${inner}</div>
        </div>`;
}

function _r2PortfolioPanel(p) {
    let inner;
    if (!p || !p.applicable) {
        inner = `
            <div class="r2-pf-cta">
                <div class="r2-pf-cta-icon"><svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2v20M2 12h20"/></svg></div>
                <div class="r2-pf-cta-text">${escapeHtml((p && p.summary) || 'Add stocks to your watchlist to see portfolio impact.')}</div>
            </div>`;
    } else if (p.exposure_count === 0) {
        inner = `
            <div class="r2-pf-clear">
                <div class="r2-pf-clear-badge">No direct exposure</div>
                <div class="r2-pf-clear-text">${escapeHtml(p.summary)}</div>
            </div>`;
    } else {
        const bull = p.net_move_pct >= 0;
        inner = `
            <div class="r2-pf-gauge">
                <div class="r2-pf-net ${bull ? 'bull' : 'bear'}">${bull ? '+' : ''}${Number(p.net_move_pct).toFixed(2)}%</div>
                <div class="r2-pf-net-label">Est. equal-weight impact on your watchlist</div>
                <div class="r2-pf-expo"><span class="r2-pf-expo-num">${p.exposure_count}</span><span class="r2-pf-expo-of">/ ${p.total} names exposed</span></div>
            </div>
            <div class="r2-pf-hits">${p.hits.map(_r2StockRow).join('')}</div>`;
    }
    return `
        <div class="r2-panel r2-panel--pf" style="--r2-accent:var(--accent-bright);">
            <div class="r2-panel-head">
                <div class="r2-panel-title">Portfolio Impact</div>
                <div class="r2-panel-sub">How this lands on your watchlist</div>
            </div>
            <div class="r2-panel-body">${inner}</div>
        </div>`;
}

function _r2ActionBanner(a) {
    if (!a) return '';
    const stateCls = { ACTIONABLE: 'go', LIVE: 'live', INFO: 'info' }[a.state] || 'info';
    const urgCls = { HIGH: 'high', MEDIUM: 'med', LOW: 'low' }[a.urgency] || 'low';
    return `
        <div class="r2-action r2-action--${stateCls}">
            <div class="r2-action-left">
                <span class="r2-action-state">${escapeHtml(a.label || a.state || '')}</span>
                <span class="r2-action-detail">${escapeHtml(a.detail || '')}</span>
            </div>
            <div class="r2-action-right">
                <div class="r2-action-chip"><span class="r2-chip-k">Horizon</span><span class="r2-chip-v">${escapeHtml(a.horizon || '—')}</span></div>
                <div class="r2-action-chip r2-urg-${urgCls}"><span class="r2-chip-k">Urgency</span><span class="r2-chip-v">${escapeHtml(a.urgency || '—')}</span></div>
            </div>
        </div>`;
}

function _renderRipple2(data) {
    const body = document.getElementById('r2-body');
    if (!body) return;
    const pct = Number(data.pct || 0);
    const up = pct >= 0;
    const shock = (data.shock_level || '').toString();
    const shockCls = shock.toUpperCase() === 'MAJOR' ? 'major' : (shock ? 'significant' : 'info');

    body.innerHTML = `
        <div class="r2-header">
            <div class="r2-kicker"><span class="r2-kicker-dot"></span>THE RIPPLE 2.0 · QUANTITATIVE CASCADE</div>
            <div class="r2-title-row">
                <h2 class="r2-title">${escapeHtml(data.instrument || 'Macro event')}</h2>
                <span class="r2-headline-move ${up ? 'bull' : 'bear'}">${up ? '+' : ''}${pct.toFixed(2)}%</span>
                ${shock ? `<span class="r2-shock-badge ${shockCls}">${escapeHtml(shock)} shock</span>` : ''}
            </div>
            <p class="r2-summary">${escapeHtml(data.summary || '')}</p>
        </div>
        ${_r2ActionBanner(data.action_window)}
        <div class="r2-grid">
            ${_r2NodeListPanel('Direct Impact', 'Mechanically tied to the move', data.direct, 'var(--green)')}
            ${_r2NodeListPanel('Second-Order', 'Supply-chain & financing transmission', data.second_order, '#60a5fa')}
            ${_r2SectorPanel(data.sector)}
            ${_r2PortfolioPanel(data.portfolio)}
        </div>
        <div class="r2-foot">Deterministic transmission model · expected moves are beta-scaled estimates, not guarantees · not investment advice.</div>`;
}

async function openRipple2(eventId) {
    const modal = document.getElementById('ripple2-modal');
    const body = document.getElementById('r2-body');
    if (!modal) return;
    if (body) {
        body.innerHTML = `
            <div class="r2-loading">
                <div class="r2-loading-ring"></div>
                <div class="r2-loading-text">Modelling the cascade<span class="ripple-dots"><span>.</span><span>.</span><span>.</span></span></div>
            </div>`;
    }
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';

    try {
        const tickers = _r2WatchlistTickers();
        const q = tickers.length ? `?tickers=${encodeURIComponent(tickers.join(','))}` : '';
        const res = await fetch(`/api/macro/events/${eventId}/ripple2${q}`);
        if (!res.ok) {
            const errBody = await res.json().catch(() => ({}));
            if (body) body.innerHTML = `<div class="r2-error"><div class="r2-error-title">Couldn’t model this cascade</div><div class="r2-error-sub">${escapeHtml(errBody.error || ('HTTP ' + res.status))}</div></div>`;
            return;
        }
        const data = await res.json();
        _renderRipple2(data);
    } catch (err) {
        if (body) body.innerHTML = `<div class="r2-error"><div class="r2-error-title">Couldn’t model this cascade</div><div class="r2-error-sub">${escapeHtml(String(err && err.message ? err.message : err))}</div></div>`;
    }
}

function closeRipple2() {
    const modal = document.getElementById('ripple2-modal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
}

document.addEventListener('click', (e) => {
    if (e.target.closest('[data-close-ripple2]')) closeRipple2();
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const m = document.getElementById('ripple2-modal');
        if (m && !m.classList.contains('hidden')) closeRipple2();
    }
});

window.openRipple2 = openRipple2;
window.closeRipple2 = closeRipple2;

// ════════════════════════════════════════════════════════════════════════
// MACRO PULSE — live shock detector strip
// Fetches /api/macro/events and renders chips for each detected shock.
// Click → opens the Ripple modal using the macro-event variant.
// Refreshes every 90 seconds.
// ════════════════════════════════════════════════════════════════════════

