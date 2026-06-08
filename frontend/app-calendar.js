function _calFormatDate(yyyyMmDd) {
    const d = new Date(yyyyMmDd + 'T00:00:00');
    const day = d.getDate();
    const month = d.toLocaleString('en-IN', { month: 'short' });
    const weekday = d.toLocaleString('en-IN', { weekday: 'long' });
    return { day, month, weekday, dateLabel: `${day} ${month}` };
}

function _calIsoEventDt(ev) {
    if (!ev || !ev.event_date) return null;
    const time = (ev.event_time_ist || '').match(/^(\d{2}):(\d{2})/);
    if (!time) return null;
    // event_date in YYYY-MM-DD, time in HH:MM IST. Build a UTC moment by
    // adjusting -5:30 from IST.
    const [Y, M, D] = ev.event_date.split('-').map(n => parseInt(n, 10));
    const hr = parseInt(time[1], 10);
    const mn = parseInt(time[2], 10);
    // Convert IST → UTC by subtracting 5:30
    const utc = Date.UTC(Y, M - 1, D, hr, mn) - (5 * 60 + 30) * 60 * 1000;
    return new Date(utc);
}

function _calMatchesFilter(ev, filter) {
    if (filter === 'all') return true;
    if (filter === 'HIGH') return (ev.importance || '').toUpperCase() === 'HIGH';
    if (filter === 'IN' || filter === 'US') return (ev.country || '').toUpperCase() === filter;
    if (filter === 'CENTRAL_BANK') return (ev.category || '').toUpperCase() === 'CENTRAL_BANK';
    return true;
}

function setCalendarFilter(f) {
    _calFilter = f;
    document.querySelectorAll('#view-calendar .sector-pill').forEach(el => el.classList.remove('active'));
    const map = { 'all': 'cal-filter-all', 'HIGH': 'cal-filter-high', 'IN': 'cal-filter-in', 'US': 'cal-filter-us', 'CENTRAL_BANK': 'cal-filter-cb' };
    const btn = document.getElementById(map[f]);
    if (btn) btn.classList.add('active');
    _renderCalendar();
}

function _renderCalendar() {
    const wrap = document.getElementById('calendar-days');
    if (!wrap || !_calData) return;
    const byDay = _calData.by_day || {};
    const today = (_calData.today_ist || '').toString();
    const dates = Object.keys(byDay).sort();
    if (!dates.length) {
        wrap.innerHTML = '<div class="glass-panel p-8 rounded-2xl text-center text-slate-400">No upcoming events in the window. Check back next week.</div>';
        return;
    }
    let html = '';
    let totalShown = 0;
    for (const date of dates) {
        const events = (byDay[date] || []).filter(e => _calMatchesFilter(e, _calFilter));
        if (!events.length) continue;
        totalShown += events.length;
        const dt = _calFormatDate(date);
        const isToday = (date === today);
        const isPast  = (date < today);
        const highCount = events.filter(e => (e.importance || '').toUpperCase() === 'HIGH').length;
        html += `
            <div class="cal-day">
                <div class="cal-day-header">
                    <div>
                        <span class="cal-day-date">${dt.day} ${dt.month}</span>
                        <span class="cal-day-weekday">${dt.weekday}</span>
                        ${isToday ? '<span class="cal-day-today"><svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor" style="vertical-align:-1px;margin-right:3px"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg>Today</span>' : ''}
                        ${isPast && !isToday ? '<span class="cal-day-today" style="background:rgba(148,163,184,0.10);border-color:rgba(148,163,184,0.20);color:#94a3b8;">Past</span>' : ''}
                    </div>
                    <div class="cal-day-meta">${events.length} event${events.length === 1 ? '' : 's'}${highCount ? ` · ${highCount} HIGH` : ''}</div>
                </div>
                ${events.map(_calRenderEvent).join('')}
            </div>
        `;
    }
    if (!totalShown) {
        html = '<div class="glass-panel p-8 rounded-2xl text-center text-slate-400">No events match this filter.</div>';
    }
    wrap.innerHTML = html;
    // Click handlers
    wrap.querySelectorAll('[data-cal-event-id]').forEach(el => {
        el.addEventListener('click', () => openCalendarEvent(parseInt(el.getAttribute('data-cal-event-id'), 10)));
    });
}

function _calRenderEvent(ev) {
    const time = ev.event_time_ist || 'TBD';
    const importance = (ev.importance || 'MEDIUM').toUpperCase();
    const country = (ev.country || '').toUpperCase();
    const desc = ev.description || '';
    const prior = ev.prior_value || '';
    const consensus = ev.consensus_estimate || '';
    const dataLine = (prior || consensus) ? `
        <div class="cal-event-data">
            ${prior     ? `<span>Prior: <b>${escapeHtml(prior)}</b></span>` : ''}
            ${consensus ? `<span>Consensus: <b>${escapeHtml(consensus)}</b></span>` : ''}
        </div>` : '';
    return `
        <div class="cal-event" data-cal-event-id="${ev.id}">
            <div>
                <div class="cal-event-time">${escapeHtml(time)}</div>
                <div class="cal-event-time-label">IST</div>
            </div>
            <div class="cal-event-main">
                <div class="cal-event-row1">
                    <span class="cal-event-title">${escapeHtml(ev.title)}</span>
                    ${country ? `<span class="cal-flag ${country}">${country}</span>` : ''}
                    <span class="cal-importance ${importance}">
                        <span class="cal-importance-dot"></span>
                        ${importance}
                    </span>
                </div>
                <div class="cal-event-desc">${escapeHtml(desc.slice(0, 180))}${desc.length > 180 ? '…' : ''}</div>
                ${dataLine}
            </div>
            <div class="cal-event-cta">
                <div class="cal-event-arrow">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>
                </div>
            </div>
        </div>
    `;
}

function openCalendarEvent(eventId) {
    const modal = document.getElementById('cal-event-modal');
    const body  = document.getElementById('cal-event-body');
    if (!modal || !body) return;
    updateAppHeaderOffset();
    const shell = modal.querySelector('.cal-event-shell');
    if (shell) shell.scrollTop = 0;
    body.innerHTML = '<div class="text-slate-400 p-8 text-center text-sm">Loading event details…</div>';
    modal.classList.remove('hidden');
    requestAnimationFrame(updateAppHeaderOffset);
    fetch(`/api/calendar/${eventId}`)
        .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
        .then(ev => {
            _renderCalEventDetail(body, ev);
            requestAnimationFrame(() => {
                if (shell) shell.scrollTop = 0;
            });
        })
        .catch(err => { body.innerHTML = `<div class="text-rose-300 p-8">Could not load event: ${escapeHtml(String(err))}</div>`; });
}

function closeCalendarEvent() {
    const modal = document.getElementById('cal-event-modal');
    if (!modal) return;
    modal.classList.add('hidden');
}

function _renderCalEventDetail(container, ev) {
    const importance = (ev.importance || 'MEDIUM').toUpperCase();
    const country = (ev.country || '').toUpperCase();
    const scenarios = ev.scenarios || {};
    const analogues = ev.historical_analogues || [];
    const sectors = ev.related_sectors || [];
    const tickers = ev.related_tickers || [];
    const upside = scenarios.upside || {};
    const expected = scenarios.expected || {};
    const downside = scenarios.downside || {};

    container.innerHTML = `
        <div class="cal-detail-kicker">
            <span class="ripple-pulse"></span>
            <span>${country ? `<span class="cal-flag ${country}" style="margin-right:6px">${country}</span>` : ''} ${escapeHtml(ev.category || 'EVENT').replace('_', ' ')}</span>
        </div>
        <h2 class="cal-detail-title">${escapeHtml(ev.title)}</h2>
        <div class="cal-detail-meta">
            <span><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:4px"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/></svg><b>${escapeHtml(ev.event_date)}</b></span>
            <span><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:4px"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg><b>${escapeHtml(ev.event_time_ist || 'TBD')} IST</b></span>
            <span><span class="cal-importance ${importance}"><span class="cal-importance-dot"></span>${importance}</span></span>
        </div>

        <div class="cal-detail-section">
            <div class="cal-detail-section-title">Overview</div>
            <div class="cal-detail-desc">${escapeHtml(ev.description || 'No description provided.')}</div>
            <div class="cal-detail-stats">
                <div class="cal-detail-stat">
                    <div class="cal-detail-stat-label">Prior</div>
                    <div class="cal-detail-stat-value">${escapeHtml(ev.prior_value || '—')}</div>
                </div>
                <div class="cal-detail-stat">
                    <div class="cal-detail-stat-label">Consensus Estimate</div>
                    <div class="cal-detail-stat-value">${escapeHtml(ev.consensus_estimate || '—')}</div>
                </div>
            </div>
        </div>

        <div class="cal-detail-section">
            <div class="cal-detail-section-title">Scenarios & Market Impact</div>
            <div class="cal-scenarios">
                ${_calRenderScenario('upside',   '↑ Upside',   upside)}
                ${_calRenderScenario('expected', '◆ Expected', expected)}
                ${_calRenderScenario('downside', '↓ Downside', downside)}
            </div>
        </div>

        ${analogues.length ? `
        <div class="cal-detail-section">
            <div class="cal-detail-section-title">Historical Analogues</div>
            ${analogues.map(a => `
                <div class="cal-analogue">
                    <span class="cal-analogue-bullet"></span>
                    <div>${escapeHtml(a)}</div>
                </div>
            `).join('')}
        </div>
        ` : ''}

        ${(sectors.length || tickers.length) ? `
        <div class="cal-detail-section">
            <div class="cal-detail-section-title">Affected</div>
            ${sectors.length ? `
                <div style="font-size:11px;color:#94a3b8;margin-bottom:6px;letter-spacing:0.10em;text-transform:uppercase;">Sectors</div>
                <div class="cal-chip-row">${sectors.map(s => `<span class="cal-chip">${escapeHtml(s)}</span>`).join('')}</div>
            ` : ''}
            ${tickers.length ? `
                <div style="font-size:11px;color:#94a3b8;margin:14px 0 6px;letter-spacing:0.10em;text-transform:uppercase;">Tickers to watch</div>
                <div class="cal-chip-row">${tickers.map(t => `<span class="cal-chip ticker">${escapeHtml(t)}</span>`).join('')}</div>
            ` : ''}
        </div>
        ` : ''}
    `;
}

function _calRenderScenario(cls, label, sc) {
    if (!sc || !sc.impact) {
        return `
            <div class="cal-scenario ${cls}">
                <div class="cal-scenario-head">
                    <span class="cal-scenario-name">${label}</span>
                </div>
                <div class="cal-scenario-impact" style="color:#64748b;font-style:italic;">No scenario provided.</div>
            </div>
        `;
    }
    const prob = (typeof sc.probability === 'number') ? Math.round(sc.probability * 100) + '%' : null;
    return `
        <div class="cal-scenario ${cls}">
            <div class="cal-scenario-head">
                <span class="cal-scenario-name">${label}</span>
                ${prob ? `<span class="cal-scenario-prob">${prob}</span>` : ''}
            </div>
            ${sc.threshold && sc.threshold !== '—' ? `<div class="cal-scenario-threshold">${escapeHtml(sc.threshold)}</div>` : ''}
            <div class="cal-scenario-impact">${escapeHtml(sc.impact)}</div>
        </div>
    `;
}

// Countdown to the next HIGH-importance event
function _calStartCountdown() {
    if (_calCountdownTimer) { clearInterval(_calCountdownTimer); _calCountdownTimer = null; }
    if (!_calData || !_calData.events) return;
    const now = Date.now();
    const upcoming = _calData.events
        .filter(e => (e.importance || '').toUpperCase() === 'HIGH')
        .map(e => ({ ev: e, ts: _calIsoEventDt(e) }))
        .filter(x => x.ts && x.ts.getTime() > now)
        .sort((a, b) => a.ts.getTime() - b.ts.getTime());
    const wrap = document.getElementById('cal-next-countdown');
    if (!wrap) return;
    if (!upcoming.length) {
        wrap.classList.add('hidden');
        return;
    }
    const next = upcoming[0];
    const clockEl = document.getElementById('cal-countdown-clock');
    const eventEl = document.getElementById('cal-countdown-event');
    if (eventEl) eventEl.innerText = next.ev.title;
    wrap.classList.remove('hidden');
    const tick = () => {
        const diff = next.ts.getTime() - Date.now();
        if (diff <= 0) {
            if (clockEl) clockEl.innerText = 'LIVE NOW';
            clearInterval(_calCountdownTimer);
            return;
        }
        const days  = Math.floor(diff / 86400000);
        const hours = Math.floor((diff % 86400000) / 3600000);
        const mins  = Math.floor((diff % 3600000) / 60000);
        const secs  = Math.floor((diff % 60000) / 1000);
        let label;
        if (days > 0) label = `${days}d ${String(hours).padStart(2,'0')}h ${String(mins).padStart(2,'0')}m`;
        else label = `${String(hours).padStart(2,'0')}:${String(mins).padStart(2,'0')}:${String(secs).padStart(2,'0')}`;
        if (clockEl) clockEl.innerText = label;
    };
    tick();
    _calCountdownTimer = setInterval(() => { if (!document.hidden) tick(); }, 1000);
}

async function fetchCalendar() {
    try {
        // Done events are dropped server-side, so only forward catalysts return.
        const r = await fetch('/api/calendar?days=14&past=0');
        if (!r.ok) throw new Error('HTTP ' + r.status);
        _calData = await r.json();
        _renderCalendar();
        _calStartCountdown();
    } catch (e) {
        const wrap = document.getElementById('calendar-days');
        if (wrap) wrap.innerHTML = `<div class="glass-panel p-8 rounded-2xl text-center text-rose-300">Could not load calendar: ${escapeHtml(String(e))}</div>`;
    }
}

// Boot — fetch on first visit to the Calendar tab + every 5 minutes thereafter.
let _calBooted = false;
const _origSwitchTabCal = window.switchTab;
if (typeof _origSwitchTabCal === 'function') {
    window.switchTab = function (tab) {
        _origSwitchTabCal.apply(this, arguments);
        if (tab === 'calendar' && !_calBooted) {
            _calBooted = true;
            fetchCalendar();
            setInterval(() => { if (!document.hidden) fetchCalendar(); }, 5 * 60 * 1000);
        }
    };
}

// Modal close handlers
document.addEventListener('click', (e) => {
    if (e.target.closest('[data-close-cal]')) closeCalendarEvent();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeCalendarEvent(); });
window.addEventListener('resize', updateAppHeaderOffset);
window.addEventListener('scroll', () => {
    const modal = document.getElementById('cal-event-modal');
    if (modal && !modal.classList.contains('hidden')) updateAppHeaderOffset();
}, { passive: true });

// Hide Navigation Bar on scroll down, show on scroll up
let lastScrollY = Math.max(0, window.scrollY);
const navEl = document.querySelector('nav.glass-panel');

window.addEventListener('scroll', () => {
    const currentScrollY = Math.max(0, window.scrollY);
    
    if (currentScrollY > lastScrollY && currentScrollY > 50) {
        // Scrolling down -> hide nav
        if (navEl && !navEl.classList.contains('nav-hidden')) {
            navEl.classList.add('nav-hidden');
            if (typeof updateAppHeaderOffset === 'function') {
                updateAppHeaderOffset();
            }
        }
    } else if (currentScrollY < lastScrollY) {
        // Scrolling up -> show nav
        if (navEl && navEl.classList.contains('nav-hidden')) {
            navEl.classList.remove('nav-hidden');
            if (typeof updateAppHeaderOffset === 'function') {
                updateAppHeaderOffset();
            }
        }
    }
    
    lastScrollY = currentScrollY;
}, { passive: true });

window.openCalendarEvent = openCalendarEvent;
window.closeCalendarEvent = closeCalendarEvent;
window.setCalendarFilter = setCalendarFilter;
window.fetchCalendar = fetchCalendar;
