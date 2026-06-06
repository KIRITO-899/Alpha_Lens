        async function fetchLiveNews() {
            try {
                // T1.4: Use the warm-fetch promise from <head> on the first call
                // (saves 100-500ms because the request was already in flight while
                // the rest of HTML/JS was parsing). Subsequent polls hit /api/news/all
                // normally.
                let payload;
                if (window.__alphaWarmFetches && window.__alphaWarmFetches.news) {
                    payload = await window.__alphaWarmFetches.news;
                    window.__alphaWarmFetches.news = null;  // consume once
                }
                if (!payload) {
                    const response = await fetch('/api/news/all?limit=7500&lite=1');
                    payload = await response.json();
                }
                // Handle both old array format and new {market_open, news} format
                let raw;
                if (Array.isArray(payload)) {
                    raw = payload;
                } else {
                    raw = payload.news || [];
                    marketOpen = !!payload.market_open;
                }
                // Deduplicate by headline — keep newest, merge stocks from duplicates
                const map = new Map();
                raw.forEach(item => {
                    const key = item.headline.trim().toLowerCase();
                    if (!map.has(key)) {
                        map.set(key, { ...item, affected_stocks: [...(item.affected_stocks || [])] });
                    } else {
                        // Merge stocks from duplicate into existing entry
                        const existing = map.get(key);
                        const existTickers = new Set(existing.affected_stocks.map(s => s.ticker));
                        (item.affected_stocks || []).forEach(s => {
                            if (!existTickers.has(s.ticker)) {
                                existing.affected_stocks.push(s);
                                existTickers.add(s.ticker);
                            }
                        });
                        // Keep the entry with the latest publication date
                        if (getNewsDate(item) > getNewsDate(existing)) {
                            existing.created_at = item.created_at;
                            existing.news_time = item.news_time;
                        }
                    }
                });
                // Sort latest first (using real publication dates)
                globalNewsData = Array.from(map.values()).sort((a, b) => getNewsDate(b) - getNewsDate(a));
                if (globalNewsData.length === 0) {
                    document.getElementById('dashboard-news-list').innerHTML = '<div class="text-slate-400 text-sm py-4 col-span-3">AI Engine is processing live feeds. Check back shortly.</div>';
                }
                const thLivePrice = document.getElementById('th-live-price');
                if (thLivePrice) {
                    thLivePrice.innerText = 'Current Price / Δ%';
                }
                renderDashboardView();
                renderArchiveView();
                renderMajorStocksView();
                renderPortfolioView();
                updatePortfolioAssistantState();
            } catch (error) { console.error("Failed to fetch news:", error); }
        }

        function renderDashboardView() {
            const container = document.getElementById('dashboard-news-list');
            container.innerHTML = '';
            // Show top 3 news — in non-stock mode still show all news headlines, badges hidden by CSS
            const topNews = globalNewsData.slice(0, 3);
            if (topNews.length === 0) {
                container.innerHTML = '<div class="text-slate-400 text-sm py-4 col-span-3">AI Engine is processing live feeds. Check back shortly.</div>';
                return;
            }
            topNews.forEach((newsItem) => {
                const div = document.createElement('div');
                const key = getNewsKey(newsItem);
                div.dataset.newsKey = key;
                div.className = `headline-tile cursor-pointer flex flex-col gap-2 ${selectedHeadlineKey === key ? 'is-active' : ''}`;
                const dt = getNewsDate(newsItem);
                const timeLabel = !isNaN(dt) ? dt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }) : '';
                const dateLabel = !isNaN(dt) ? dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '';
                div.innerHTML = `
                    <div class="flex items-center gap-1.5 text-[9px] text-violet-400 font-mono">
                        <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        ${dateLabel} · ${timeLabel}
                    </div>
                    <h4 class="text-xs font-bold text-slate-200 line-clamp-2">${escapeHtml(newsItem.headline)}</h4>
                `;
                div.onclick = () => loadArticleIntoMainViewer(newsItem);
                container.appendChild(div);
            });
            if (globalNewsData.length > 0) loadArticleIntoMainViewer(globalNewsData[0]);
        }

        function getImpactColorClasses(impact) {
            const i = (impact || '').toLowerCase();
            if (i === 'bullish') return "bg-green-800/60 text-green-300 border-green-500/80 shadow-[0_0_15px_rgba(34,197,94,0.3)]";
            if (i === 'slightly bullish') return "bg-emerald-900/50 text-emerald-300 border-emerald-500/60 shadow-[0_0_10px_rgba(52,211,153,0.2)]";
            if (i === 'bearish') return "bg-red-800/60 text-red-300 border-red-500/80 shadow-[0_0_15px_rgba(239,68,68,0.3)]";
            if (i === 'slightly bearish') return "bg-orange-900/50 text-orange-300 border-orange-500/60 shadow-[0_0_10px_rgba(251,146,60,0.2)]";
            return "bg-slate-800/60 text-slate-300 border-white/5";
        }

        function getStatusBadge(status) {
            if (status === 'Predicted Target Hit') return { text: '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" style="vertical-align:-1px;margin-right:3px"><path d="M5 13l4 4L19 7"/></svg>Target Hit', cls: 'text-green-400' };
            if (status === 'Stop Loss Hit') return { text: '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" style="vertical-align:-1px;margin-right:3px"><path d="M6 6l12 12M18 6L6 18"/></svg>Stop Loss Hit', cls: 'text-red-400' };
            if (status === 'Reacted Against Prediction') return { text: '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" style="vertical-align:-1px;margin-right:3px"><path d="M6 6l12 12M18 6L6 18"/></svg>Stop Loss Hit', cls: 'text-red-400' };
            return { text: '● Active View', cls: 'text-violet-400' };
        }

        function getConfidenceBadge(score) {
            const val = score || 80;
            let cls = "text-red-400 border-red-500/30 bg-red-900/10";
            let label = "Speculative";
            if (val >= 85) { cls = "text-green-400 border-green-500/30 bg-green-900/10"; label = "High Veracity"; }
            else if (val >= 60) { cls = "text-amber-400 border-amber-500/30 bg-amber-900/10"; label = "Moderate"; }
            return `<div class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-[9px] font-bold uppercase tracking-wider ${cls}">
                <span class="w-1 h-1 rounded-full bg-current animate-pulse"></span>
                ${label} ${val}%
            </div>`;
        }

        function markActiveHeadline(newsItem) {
            const key = getNewsKey(newsItem);
            document.querySelectorAll('.headline-tile').forEach(tile => {
                tile.classList.toggle('is-active', tile.dataset.newsKey === key);
            });
        }

        function setInsightText(id, value) {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        }

        function updateHeroInsightPanel(newsItem) {
            const stocks = Array.isArray(newsItem?.affected_stocks) ? newsItem.affected_stocks : [];
            const scores = stocks.map(s => Number(s.confidence_score)).filter(n => !Number.isNaN(n));
            const conviction = scores.length ? Math.round(scores.reduce((sum, n) => sum + n, 0) / scores.length) : 72;
            const bullish = stocks.filter(s => (s.impact || '').toLowerCase().includes('bullish')).length;
            const bearish = stocks.filter(s => (s.impact || '').toLowerCase().includes('bearish')).length;
            const bias = bullish > bearish ? 'Bullish' : bearish > bullish ? 'Bearish' : 'Neutral';
            const dt = getNewsDate(newsItem);
            const freshness = !isNaN(dt) ? dt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }) : '--';

            setInsightText('hero-conviction', `${conviction}%`);
            setInsightText('hero-assets', String(stocks.length));
            setInsightText('hero-bias', bias);
            setInsightText('hero-bias-note', stocks.length ? `${bullish} bullish / ${bearish} bearish` : 'no direct equity signal');
            setInsightText('hero-freshness', freshness);

            const bar = document.getElementById('hero-conviction-bar');
            if (bar) bar.style.width = `${Math.min(100, Math.max(0, conviction))}%`;

            const notes = document.getElementById('hero-desk-notes');
            if (!notes) return;
            const topStock = stocks[0];
            // Note 3 — dynamic assessment of the macro correlation regime
            const noteItems = [
                topStock ? `Primary watch: ${topStock.ticker} is tagged ${topStock.impact || 'under review'}.` : 'No direct stock impact has been detected yet.',
                `Bias read: ${bias} across ${stocks.length} linked asset${stocks.length === 1 ? '' : 's'}.`,
                topStock ? `Regime transmission: High confidence shock wave cascade predicted.` : 'Regime transmission: Nominal regime, volatility is baseline.'
            ];
            notes.innerHTML = noteItems.map((note, idx) => `
                <div class="insight-tile">
                    <div class="insight-label">Note ${idx + 1}</div>
                    <p class="mt-2 text-sm text-slate-300 leading-relaxed">${escapeHtml(note)}</p>
                </div>
            `).join('');
        }

        function loadArticleIntoMainViewer(newsItem) {
            selectedHeadlineKey = getNewsKey(newsItem);
            markActiveHeadline(newsItem);
            updateHeroInsightPanel(newsItem);
            document.getElementById('main-headline-text').innerText = newsItem.headline;
            // Plain English Decode — Dynamic extraction with fallbacks
            const aamEl = document.getElementById('aam-janta-text');
            if (aamEl) {
                if (newsItem.aam_janta_translation && newsItem.aam_janta_translation !== 'Paused for saving keys for now') {
                    aamEl.innerText = newsItem.aam_janta_translation;
                } else if (newsItem.explanation) {
                    aamEl.innerText = newsItem.explanation;
                } else {
                    const cat = newsItem.category ? `within the ${newsItem.category} sector` : 'across key sectors';
                    aamEl.innerText = `This systemic development ${cat} triggers algorithmic and positioning shifts across correlated Indian equities. Monitor active price feeds and volume breakouts for entry-level executions.`;
                }
            }
            // Full article body — hidden when empty so the panel doesn't show
            // an empty box. Source is the RSS summary (or scraped body), set
            // by the AI worker at insert time.
            const bodyText = (newsItem.body || '').trim();
            const bodyEl = document.getElementById('main-article-body');
            const bodyWrap = document.getElementById('main-article-body-wrap');
            if (bodyEl && bodyWrap) {
                if (bodyText) {
                    bodyEl.innerText = bodyText;
                    bodyWrap.classList.remove('hidden');
                } else {
                    bodyEl.innerText = '';
                    bodyWrap.classList.add('hidden');
                }
            }
            // Macro Impact Flow — Render the actual propagation pathway dynamically!
            let steps = ['Macro Trigger', 'Primary Hit', 'Supply Chain', 'Macro Transmission'];
            if (Array.isArray(newsItem.macro_pathway) && newsItem.macro_pathway.length >= 4 && 
                !newsItem.macro_pathway.some(s => typeof s === 'string' && s.includes('Paused'))) {
                steps = newsItem.macro_pathway;
            } else if (newsItem.affected_stocks && newsItem.affected_stocks.length > 0) {
                const stocks = newsItem.affected_stocks;
                const triggerStr = newsItem.category ? `${escapeHtml(newsItem.category)} Shock` : 'Macro Trigger';
                const primStr = stocks[0] ? `${escapeHtml(stocks[0].ticker)} (${escapeHtml(stocks[0].impact || 'Direct')})` : 'Direct Impact';
                const ripStr = stocks[1] ? `${escapeHtml(stocks[1].ticker)} (${escapeHtml(stocks[1].impact || 'Indirect')})` : (stocks[0] ? 'Supply Chain' : 'Second-Order');
                const macStr = stocks[2] ? `${escapeHtml(stocks[2].ticker)} (Transmission)` : (stocks[1] ? 'Macro Effect' : 'Transmission');
                steps = [triggerStr, primStr, ripStr, macStr];
            } else {
                const hl = newsItem.headline || '';
                let trigger = 'Market Trigger';
                if (hl.toLowerCase().includes('crude') || hl.toLowerCase().includes('oil')) trigger = 'Energy Trigger';
                else if (hl.toLowerCase().includes('gold') || hl.toLowerCase().includes('silver')) trigger = 'Bullion Trigger';
                else if (hl.toLowerCase().includes('rbi') || hl.toLowerCase().includes('rate') || hl.toLowerCase().includes('fed')) trigger = 'Monetary Policy';
                else if (hl.toLowerCase().includes('nifty')) trigger = 'Equity Benchmark';
                
                steps = [
                    trigger,
                    'Sector Impact',
                    'Equity Cascade',
                    'Systemic Flow'
                ];
            }

            ['path-1', 'path-2', 'path-3', 'path-4'].forEach((id, idx) => {
                const el = document.getElementById(id);
                if (el) el.innerText = steps[idx];
            });
            const tableBody = document.getElementById('dynamic-stock-table-body');
            tableBody.innerHTML = '';
            if (!newsItem.affected_stocks || newsItem.affected_stocks.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="4" class="py-4 text-center text-slate-500">No specific stocks identified for this news.</td></tr>';
                return;
            }
            newsItem.affected_stocks.forEach(stock => {
                const colorClasses = getImpactColorClasses(stock.impact);
                const basePrice = parseFloat(stock.base_price);
                const currentPrice = parseFloat(stock.current_price);
                const hasPrice = !isNaN(basePrice) && basePrice > 0;
                const hasCurrent = !isNaN(currentPrice) && currentPrice > 0;

                const isResolved = ['Stop Loss Hit', 'Predicted Target Hit', 'Reacted Against Prediction'].includes(stock.status);
                const isExpired = stock.status === 'Expired';
                const isClosed = isResolved || isExpired;

                // Market change is always current value vs previous close.
                const diffPct = (stock.diff_pct != null) ? stock.diff_pct
                    : (stock.market_change_pct != null) ? stock.market_change_pct
                    : (hasPrice && hasCurrent ? ((currentPrice - basePrice) / basePrice * 100) : null);
                const diffPctStr = diffPct !== null ? (diffPct >= 0 ? '+' : '') + diffPct.toFixed(2) + '%' : '—';
                const diffColorCls = diffPct === null ? 'text-slate-400' : diffPct >= 0 ? 'text-green-400' : 'text-red-400';

                const statusBadge = getStatusBadge(stock.status);
                const tr = document.createElement('tr');
                tr.style.opacity = isClosed ? '0.85' : '1';

                // ── Closed banner (shown above status for resolved/expired signals) ──
                const closedBanner = isClosed
                    ? `<div class="inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest px-2 py-0.5 rounded mb-1"
                           style="background:rgba(148,163,184,0.15);color:#94a3b8;border:1px solid rgba(148,163,184,0.3)">
                           ◼ SIGNAL CLOSED
                       </div><br>`
                    : '';

                // ── Live / price-only badge (in current price column) ──
                const priceBadge = (marketOpen && stock.status === 'Active View')
                    ? `<div class="text-[8px] font-bold mt-1" style="color:#4ade80">● LIVE PRICE</div>`
                    : isClosed
                        ? `<div class="text-[8px] font-bold mt-1" style="color:#64748b">← LIVE PRICE (tracking)</div>`
                        : '';

                tr.innerHTML = `
                    <td class="py-4">
                        ${closedBanner}
                        <div class="font-bold text-white text-base tracking-wide">${escapeHtml(stock.ticker)}</div>
                        <div class="flex items-center gap-2 mt-1">
                            <div class="text-[9px] font-bold ${statusBadge.cls}">${statusBadge.text}</div>
                            ${getConfidenceBadge(stock.confidence_score)}
                        </div>
                        <div class="text-[9px] text-slate-400 uppercase tracking-widest mt-1 bg-black/40 inline-block px-2 py-0.5 rounded border border-white/5">${escapeHtml(stock.view || 'Pending')}</div>
                    </td>
                    <td class="py-4 text-right">
                        <div class="text-white font-bold font-mono text-sm">${hasPrice ? '₹' + basePrice.toFixed(2) : '—'}</div>
                        ${hasPrice ? `<div class="text-[8px] text-slate-500 mt-0.5">At news time</div>` : '<div class="text-[8px] text-slate-600 mt-0.5">Market closed at news</div>'}
                    </td>
                    <td class="py-4 text-right">
                        <div class="text-white font-bold font-mono text-sm">${hasCurrent ? '₹' + currentPrice.toFixed(2) : '—'}</div>
                        <div class="font-mono text-xs font-bold ${diffColorCls} mt-0.5">${diffPctStr}</div>
                        ${priceBadge}
                    </td>
                    <td class="py-4 text-right">
                        <span class="border px-3 py-1.5 rounded-lg font-bold text-[11px] uppercase tracking-widest ${colorClasses}">${escapeHtml(stock.impact)}</span>
                    </td>
                `;
                tableBody.appendChild(tr);
            });
        }


        // ── All News virtualization state ──
        // We hold the filtered list in memory but only mount cards into the
        // DOM in batches as the sentinel scrolls into view. With ~500 cards
        // this is the difference between a 4s freeze and instant render.
        let _archiveFiltered = [];
        let _archiveRendered = 0;
        let _archiveObserver = null;
        const _ARCHIVE_BATCH_SIZE = 30;

        function _buildArchiveCard(news, cardIdx) {
            const item = document.createElement('div');
            item.className = "glass-panel news-card-hover p-6 rounded-2xl cursor-pointer";
            item.style.setProperty('--i', Math.min(cardIdx, 12));
            item.setAttribute('data-stagger-i', String(cardIdx));
            item.onclick = (e) => {
                if (e.target.closest('.ticker-hover-target')) return;
                loadArticleIntoMainViewer(news); switchTab('top-news');
            };
            const dt = getNewsDate(news);
            const dateStr = !isNaN(dt) ? dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
            const timeStr = !isNaN(dt) ? dt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }) : '—';
            let impactedStocksHtml = '';
            if (news.affected_stocks && news.affected_stocks.length > 0) {
                const seenBadgeTickers = new Set();
                news.affected_stocks.forEach(stock => {
                    const tkKey = (stock.ticker || '').toUpperCase();
                    if (seenBadgeTickers.has(tkKey)) return;
                    seenBadgeTickers.add(tkKey);
                    const impact = (stock.impact || '').toLowerCase();
                    let color = impact.includes('bullish') ? 'text-green-400 border-green-500/30 bg-green-900/10' :
                        impact.includes('slightly bearish') ? 'text-orange-400 border-orange-500/30 bg-orange-900/10' :
                            'text-red-400 border-red-500/30 bg-red-900/10';
                    impactedStocksHtml += `
                        <div class="flex flex-col gap-1">
                            <span class="ticker-hover-target text-[10px] uppercase tracking-widest font-bold border px-2 py-1 rounded ${color}" data-ticker="${escapeHtml(stock.ticker)}">${escapeHtml(stock.ticker)}</span>
                            ${getConfidenceBadge(stock.confidence_score)}
                        </div>`;
                });
            } else if (news.ai_status === 'pending') {
                // Headline saved during AI downtime — predictions will fill
                // in on the next rescreen pass.
                impactedStocksHtml = `<span class="inline-flex items-center gap-1.5 text-[10px] text-violet-300 uppercase tracking-widest font-bold border border-violet-500/40 bg-violet-900/20 px-2 py-1 rounded">
                    <span class="w-1 h-1 rounded-full bg-violet-300 animate-pulse"></span>
                    AI Analysis Pending
                </span>`;
            } else {
                impactedStocksHtml = `<span class="text-[10px] text-slate-500 uppercase tracking-widest">No direct equity impact</span>`;
            }
            // Body snippet — first ~200 chars of news.body. Backend lite mode
            // already trims server-side; this is a safety belt for very old
            // rows or non-lite responses.
            const rawBody = (news.body || '').trim();
            const bodySnippet = rawBody ? (rawBody.length > 220 ? rawBody.slice(0, 220).trim() + '…' : rawBody) : '';
            const bodyHtml = bodySnippet ? `
                <p class="text-[11px] text-slate-400 leading-relaxed mt-2 mb-3 line-clamp-3">${escapeHtml(bodySnippet)}</p>
            ` : '';
            const aamJanta = (news.aam_janta_translation || '').trim();
            const backHtml = aamJanta ? `
                <div class="nc-back">
                    <div class="nc-back-label">AI Reasoning</div>
                    <div class="nc-back-body">${escapeHtml(aamJanta.length > 320 ? aamJanta.slice(0, 320) + '…' : aamJanta)}</div>
                </div>
            ` : '';
            // "View Ripple" badge — only for big macro events. Backend sets
            // news.has_ripple = 1 after the propagation graph is generated.
            const rippleCta = news.has_ripple ? `
                <button class="ripple-cta" data-ripple-id="${news.id}" aria-label="Open propagation graph">
                    <span class="ripple-cta-icon"></span>
                    The Ripple
                    ${news.ripple_score ? `<span class="ripple-cta-score">${news.ripple_score}</span>` : ''}
                </button>
            ` : '';

            item.innerHTML = `
                <div class="nc-front">
                    <div class="flex items-center justify-between gap-2 mb-2">
                        <div class="flex items-center gap-1.5 text-[9px] text-violet-400 font-mono">
                            <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                            ${dateStr} · ${timeStr}
                        </div>
                        ${rippleCta}
                    </div>
                    <div class="flex items-start justify-between gap-4 mb-1">
                        <h3 class="text-base font-bold text-slate-100 leading-snug flex-1">${escapeHtml(news.headline)}</h3>
                    </div>
                    ${bodyHtml}
                    <div class="stock-badge-container items-center gap-3 pt-3 border-t border-white/5 transition-opacity duration-300"
                         style="display: ${isNonStockMode ? 'none' : 'flex'}">
                        <svg class="w-3.5 h-3.5 text-slate-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                        <div class="flex flex-wrap gap-2">${impactedStocksHtml}</div>
                    </div>
                </div>
                ${backHtml}
            `;
            // Wire the Ripple CTA — stop propagation so clicking the badge
            // doesn't also fire the card's "open article" handler.
            const ctaEl = item.querySelector('[data-ripple-id]');
            if (ctaEl) {
                ctaEl.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openRipple(parseInt(ctaEl.getAttribute('data-ripple-id'), 10));
                });
            }
            return item;
        }

        function _renderArchiveBatch(container) {
            const end = Math.min(_archiveRendered + _ARCHIVE_BATCH_SIZE, _archiveFiltered.length);
            const frag = document.createDocumentFragment();
            for (let i = _archiveRendered; i < end; i++) {
                frag.appendChild(_buildArchiveCard(_archiveFiltered[i], i));
            }
            // Remove the old sentinel before appending more cards
            const oldSentinel = document.getElementById('archive-load-sentinel');
            if (oldSentinel) oldSentinel.remove();
            container.appendChild(frag);
            _archiveRendered = end;
            // Add a fresh sentinel if more cards remain
            if (_archiveRendered < _archiveFiltered.length) {
                const sentinel = document.createElement('div');
                sentinel.id = 'archive-load-sentinel';
                sentinel.style.cssText = 'height:48px;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;';
                sentinel.textContent = `Loading more · ${_archiveRendered} / ${_archiveFiltered.length}`;
                container.appendChild(sentinel);
                if (_archiveObserver) _archiveObserver.observe(sentinel);
            }
        }

        function renderArchiveView() {
            const container = document.getElementById('archive-news-list');
            if (!container) return;
            container.innerHTML = '';
            _archiveRendered = 0;
            // Tear down any prior observer — we'll create a fresh one for the
            // current list so the sentinel reference doesn't leak across renders.
            if (_archiveObserver) {
                try { _archiveObserver.disconnect(); } catch (_) {}
                _archiveObserver = null;
            }

            const sevenDaysAgo = Date.now() - (168 * 60 * 60 * 1000);
            let recentNews = globalNewsData.filter(news => parseSQLiteDate(news.created_at).getTime() >= sevenDaysAgo);
            if (currentArchiveFilter !== 'all') {
                if (currentArchiveFilter.startsWith('cat:')) {
                    const targetCat = currentArchiveFilter.split(':')[1].toLowerCase();
                    recentNews = recentNews.filter(news => (news.category || 'general').toLowerCase() === targetCat);
                } else {
                    recentNews = recentNews.filter(news => {
                        const hasStocks = news.affected_stocks && news.affected_stocks.length > 0;
                        if (currentArchiveFilter === 'none') return !hasStocks;
                        if (hasStocks) {
                            return news.affected_stocks.some(stock => (stock.impact || '').toLowerCase() === currentArchiveFilter);
                        }
                        return false;
                    });
                }
            }
            _archiveFiltered = recentNews;

            const countEl = document.getElementById('news-count');
            if (countEl) countEl.innerText = `${_archiveFiltered.length} Articles`;
            if (_archiveFiltered.length === 0) {
                container.innerHTML = '<div class="glass-panel p-8 rounded-2xl text-center text-slate-400">No news found in the last 7 days. The AI engine may still be processing feeds.</div>';
                return;
            }

            // Spin up an observer that fires when the sentinel scrolls into view.
            // rootMargin pre-loads a screen ahead so the user never sees the loader
            // unless they're scrolling unreasonably fast.
            _archiveObserver = new IntersectionObserver((entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        _renderArchiveBatch(container);
                    }
                }
            }, { rootMargin: '600px 0px', threshold: 0.01 });

            _renderArchiveBatch(container);
        }

