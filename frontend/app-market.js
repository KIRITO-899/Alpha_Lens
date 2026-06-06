        function renderMajorStocksView() {
            const container = document.getElementById('all-stocks-grid');
            if (!container) return;
            container.innerHTML = '';
            let allStocks = [];
            // Use published time
            // Filter by DB insertion time (created_at), NOT stale RSS dates
            const sevenDaysAgo = Date.now() - (168 * 60 * 60 * 1000);
            const recentNews = globalNewsData.filter(n => parseSQLiteDate(n.created_at).getTime() >= sevenDaysAgo);
            recentNews.forEach(news => {
                if (news.affected_stocks && news.affected_stocks.length > 0) {
                    news.affected_stocks.forEach(stock => {
                        allStocks.push({ ...stock, headline: news.headline });
                    });
                }
            });
            // Deduplicate by ticker — keep the entry with highest confidence_score
            const tickerMap = new Map();
            allStocks.forEach(stock => {
                const key = (stock.ticker || '').toUpperCase();
                if (!tickerMap.has(key)) {
                    tickerMap.set(key, stock);
                } else {
                    const existing = tickerMap.get(key);
                    if ((stock.confidence_score || 0) > (existing.confidence_score || 0)) {
                        tickerMap.set(key, stock);
                    }
                }
            });
            allStocks = Array.from(tickerMap.values());
            const stockCountEl = document.getElementById('stock-count');
            if (stockCountEl) stockCountEl.innerText = `${allStocks.length} Identified`;
            if (allStocks.length === 0) {
                container.innerHTML = '<div class="col-span-full text-center py-12 text-slate-400">No affected stocks found. The AI engine may still be processing live feeds.</div>';
                return;
            }
            allStocks.forEach(stock => {
                const impact = (stock.impact || '').toLowerCase();
                const isBull = impact.includes('bullish');
                const isSlightly = impact.includes('slightly');
                let colorClasses, textCol;
                if (impact === 'bullish') { colorClasses = "bg-green-900/20 border-green-500/40 shadow-[0_0_15px_rgba(34,197,94,0.1)]"; textCol = "text-green-400"; }
                else if (impact === 'slightly bullish') { colorClasses = "bg-emerald-900/15 border-emerald-500/30 shadow-[0_0_10px_rgba(52,211,153,0.08)]"; textCol = "text-emerald-400"; }
                else if (impact === 'slightly bearish') { colorClasses = "bg-orange-900/15 border-orange-500/30 shadow-[0_0_10px_rgba(251,146,60,0.08)]"; textCol = "text-orange-400"; }
                else { colorClasses = "bg-red-900/20 border-red-500/40 shadow-[0_0_15px_rgba(239,68,68,0.1)]"; textCol = "text-red-400"; }

                const bp = parseFloat(stock.base_price);
                const cp = parseFloat(stock.current_price);
                const hasPrice = !isNaN(bp) && bp > 0;
                const hasCurrent = !isNaN(cp) && cp > 0;
                // Stock signal change is based on news-time base price first;
                // fallback to market change only if signal diff is unavailable.
                const diffPct = (stock.diff_pct != null) ? stock.diff_pct
                    : (stock.market_change_pct != null) ? stock.market_change_pct
                    : (hasPrice && hasCurrent ? ((cp - bp) / bp * 100) : null);
                const diffPctStr = diffPct !== null ? (diffPct >= 0 ? '+' : '') + diffPct.toFixed(2) + '%' : '—';
                const diffColorCls = diffPct === null ? 'text-slate-400' : diffPct >= 0 ? 'text-green-400' : 'text-red-400';

                const statusBadge = getStatusBadge(stock.status);
                const card = document.createElement('div');
                card.className = `p-5 rounded-2xl border ${colorClasses} hover:scale-[1.01] transition-all cursor-default relative overflow-hidden`;
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h3 class="text-xl font-bold font-display text-white tracking-widest">${escapeHtml(stock.ticker)}</h3>
                            <span class="text-[9px] uppercase font-bold ${statusBadge.cls}">${statusBadge.text}</span>
                        </div>
                        <span class="text-[10px] uppercase font-bold px-2 py-1 rounded border ${textCol} border-current">${escapeHtml(stock.impact)}</span>
                    </div>
                    <div class="grid grid-cols-3 gap-2 text-xs font-mono mb-3 bg-black/30 rounded-lg p-3">
                        <div class="text-center">
                            <div class="text-slate-500 text-[9px] uppercase mb-1">At News</div>
                            <div class="text-slate-300 font-bold">${hasPrice ? '₹' + bp.toFixed(2) : '—'}</div>
                        </div>
                        <div class="text-center">
                            <div class="text-slate-500 text-[9px] uppercase mb-1">Current Price</div>
                            <div class="text-white font-bold">${hasCurrent ? '₹' + cp.toFixed(2) : '—'}</div>
                        </div>
                        <div class="text-center">
                            <div class="text-slate-500 text-[9px] uppercase mb-1">Change</div>
                            <div class="font-bold ${diffColorCls}">${diffPctStr}</div>
                        </div>
                    </div>
                    <p class="text-xs text-slate-300 leading-relaxed mb-3 line-clamp-2">${escapeHtml(stock.reason || 'Analyzing macro flow...')}</p>
                    <div class="flex items-center gap-1 text-[9px] text-slate-500 border-t border-white/5 pt-2">
                        <svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 12h6m-6 0h.01"/></svg>
                        <span class="line-clamp-1">${escapeHtml(stock.headline)}</span>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        // playInitialWelcome() removed — the "INITIALIZING DESK ENVIRONMENT"
        // (#gsap-welcome) splash is gone. The cinematic #onboarding-overlay
        // letter-reveal is the only intro now, and the dashboard is visible
        // at its natural opacity underneath it (no gsap hide/reveal needed).

        async function fetchIndices() {
            try {
                // T1.4: Same warm-fetch pattern as fetchLiveNews — first call
                // consumes the promise that was kicked off in <head>.
                let data;
                if (window.__alphaWarmFetches && window.__alphaWarmFetches.indices) {
                    data = await window.__alphaWarmFetches.indices;
                    window.__alphaWarmFetches.indices = null;
                }
                if (!data) {
                    const res = await fetch('/api/indices');
                    data = await res.json();
                }
                const container = document.getElementById('index-ticker');
                if (!container || !data.length) return;

                // Accent colors per index (up direction)
                const accents = ['#7c3aed', '#a78bfa', '#ff9f0a', '#00d26a'];
                const isLive = data[0]?.is_live ?? true;
                const marketStatus = data[0]?.market_status ?? 'Market Open';

                container.innerHTML = data.map((idx, i) => {
                    const hasQuote = idx.price !== null && idx.price !== undefined && idx.change_pct !== null && idx.change_pct !== undefined;
                    const up = hasQuote && idx.change_pct >= 0;
                    const accentColor = accents[i];
                    const bgGrad = `linear-gradient(135deg, ${accentColor}08 0%, transparent 60%)`;
                    // Always use real change_pct from backend (backend now computes it even when closed)
                    const changeVal = hasQuote ? idx.change_pct : null;
                    const pctText = changeVal !== null ? (changeVal > 0 ? '+' : '') + changeVal.toFixed(2) + '%' : '—';
                    // Color: green if up, red if down, amber only if exactly 0
                    const pctBg = changeVal === null
                        ? 'background:rgba(148,163,184,0.12);color:#94a3b8;border:1px solid rgba(148,163,184,0.3)'
                        : changeVal >= 0
                        ? 'background:rgba(74,222,128,0.12);color:#4ade80;border:1px solid rgba(74,222,128,0.3)'
                        : 'background:rgba(248,113,113,0.12);color:#f87171;border:1px solid rgba(248,113,113,0.3)';

                    const priceFmt = idx.price !== null
                        ? idx.price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                        : '—';

                    // Live dot vs closed label
                    const statusBadge = isLive
                        ? `<span class="live-dot w-1.5 h-1.5 rounded-full inline-block" style="background:${accentColor}"></span>`
                        : `<span class="text-[8px] font-bold tracking-wider px-1.5 py-0.5 rounded" style="background:rgba(100,116,139,0.15);color:#94a3b8;border:1px solid rgba(100,116,139,0.3)">CLOSED</span>`;

                    return `
                        <div class="index-card glass-panel rounded-2xl p-4 cursor-default"
                             style="--card-accent:${accentColor};background:${bgGrad};">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-[9px] font-bold tracking-[0.15em] text-slate-400 uppercase">${escapeHtml(idx.name)}</span>
                                ${statusBadge}
                            </div>
                            <div class="text-xl font-display font-black text-white tracking-tight mb-2">${priceFmt}</div>
                            <div class="flex items-center justify-between">
                                <div class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold" style="${pctBg}">
                                    ${changeVal === null ? '&mdash;' : changeVal > 0 ? '&#9650;' : changeVal < 0 ? '&#9660;' : '&mdash;'} ${pctText}
                                </div>
                                <div class="text-[8px] font-mono text-slate-500 uppercase">${!isLive ? marketStatus : ''}</div>
                            </div>
                        </div>`;
                }).join('');
            } catch (e) { console.error('Indices fetch failed', e); }
        }

        // Market-aware polling: faster during open hours, slower when closed
        function startSmartPolling() {
            // Initial fetch
            fetchLiveNews();
            fetchIndices();
            if (typeof loadCommandBar === 'function') loadCommandBar();

            function schedulePolling() {
                // Re-check market status every tick
                const nowIST = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
                const day = nowIST.getDay(); // 0=Sun, 6=Sat
                const mins = nowIST.getHours() * 60 + nowIST.getMinutes();
                const isOpen = day >= 1 && day <= 5 && mins >= 555 && mins <= 930; // 9:15–15:30

                const newsInterval = isOpen ? 30000 : 300000;  // 30s open, 5 min closed
                const indexInterval = isOpen ? 30000 : 600000;  // 30s open, 10 min closed

                setTimeout(() => { fetchLiveNews(); scheduleNewsPolling(); }, newsInterval);
                setTimeout(() => { fetchIndices(); scheduleIndexPolling(); }, indexInterval);
            }

            function scheduleNewsPolling() {
                const nowIST = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
                const day = nowIST.getDay();
                const mins = nowIST.getHours() * 60 + nowIST.getMinutes();
                const isOpen = day >= 1 && day <= 5 && mins >= 555 && mins <= 930;
                setTimeout(() => {
                    fetchLiveNews();
                    if (typeof loadCommandBar === 'function') loadCommandBar();
                    scheduleNewsPolling();
                }, isOpen ? 30000 : 120000);
            }

            function scheduleIndexPolling() {
                const nowIST = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
                const day = nowIST.getDay();
                const mins = nowIST.getHours() * 60 + nowIST.getMinutes();
                const isOpen = day >= 1 && day <= 5 && mins >= 555 && mins <= 930;
                setTimeout(() => { fetchIndices(); updateWatchlistPrices(); scheduleIndexPolling(); }, isOpen ? 30000 : 60000);
            }

            // Kick off independent polling loops
            scheduleNewsPolling();
            scheduleIndexPolling();
        }

        window.onload = () => {
            maybeShowOnboarding();          // #3 cinematic onboarding (first session per tab)
            checkAuthStatus();
            startSmartPolling();
            renderWatchlistPanel();
            updatePortfolioAssistantState();
            updateWatchlistPrices();
            initPremiumFeatures();
            installCardFlipHandlers();      // #6 3D card flip on long-hover
        };

        // T2.12: Three.js particle background removed. The container it rendered
        // into was display:none — the aurora-mesh CSS layer handles the visible
        // background. Saves ~150 KB on every page load + a continuous 60fps
        // animation loop that was running for an invisible canvas.

        // ══════════════════════════════════════════════════════════════
        // PREMIUM FEATURES: Ticker Bar, Signal Terminal, Track Record, Toasts
        // ══════════════════════════════════════════════════════════════

        let _terminalData = [];
        let _terminalSort = { key: 'confidence', asc: false };
        let _terminalFilter = 'all';
        let _lastNotifId = 0;

