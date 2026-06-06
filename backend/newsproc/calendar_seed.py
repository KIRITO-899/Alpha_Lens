"""
Seed data for the macro / economic-events calendar — a pure static list of
event dicts (date, time, scenario analysis, related tickers). Consumed by
seed_calendar_events() in app.py, which imports CALENDAR_EVENTS_SEED back.
No logic/state here.

Next-week slate: 2026-06-08 -> 2026-06-17 (13 events). Predictions are
web-grounded and adversarially verified, then harmonized to one macro
backdrop (USD/INR ~95, Brent ~$95-97, US-Iran/Hormuz risk). Concluded
events drop off automatically — seed_calendar_events() skips already-done
entries and calendar_worker() releases+purges them.
"""


CALENDAR_EVENTS_SEED = [
    {
        "event_date": "2026-06-08",
        "event_time_ist": "11:00",
        "title": "India SW Monsoon Progress — IMD Weekly Update",
        "country": "IN",
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "description": "IMD's weekly bulletin on southwest-monsoon advance and cumulative rainfall vs the Long Period Average (seasonal LPA ~86.8 cm / ~868 mm; June LPA ~165 mm). It matters because the monsoon drives kharif sowing, rural incomes, food inflation and hydropower — the transmission chain into tractor, fertiliser, agrochem, rural-FMCG and 2-wheeler demand. The backdrop is bearish: the monsoon hit Kerala on 4 Jun 2026 (3 days late) and IMD's 29 May revision cut the seasonal forecast to a below-normal 90% of LPA (±4%) with a 60% chance of a below-normal/deficient season, amid a high (~80-95%) El Niño-development risk for the Jun-Sep window. Watch the cumulative departure-from-LPA % and whether the advance reaches Maharashtra/central India on schedule or stalls — this is a forward-looking progress update, not a final seasonal result.",
        "prior_value": "Kerala onset 4 Jun 2026 (3 days late); IMD seasonal forecast 90% of LPA (below normal, ±4% error); early-June cumulative rainfall running ~12-18% below LPA on a delayed, sluggish advance",
        "consensus_estimate": "Steady advance into Goa/Maharashtra/central India but cumulative rainfall holding ~10-20% below LPA; no upgrade from the 90%-of-LPA below-normal seasonal call",
        "scenarios": {
            "upside": {
                "threshold": "Advance accelerates and cumulative rainfall recovers to within ~5% of LPA / IMD nudges tone toward normal",
                "impact": "Rural-demand relief rally: M&M (+1.5-3%) and Escorts Kubota/ESCORTS (+2-4%) on tractor-volume hopes; fertilisers COROMANDEL (+2-3.5%) and agrochem UPL/PIIND (+1.5-3%); rural FMCG DABUR (+1-2%) and 2-wheelers HEROMOTOCO/TVSMOTOR (+1.5-3%). Cooler food-inflation outlook eases the bond-yield/INR risk premium, a mild tailwind for rate-sensitives.",
                "probability": 0.2
            },
            "expected": {
                "threshold": "Advance broadly on-track but cumulative rainfall stays ~10-20% below LPA; 90%-of-LPA below-normal call intact",
                "impact": "Muted, stock-specific reaction: agri-input and tractor names (M&M, ESCORTS, COROMANDEL, UPL) drift +/-0.5-1.5% with no clear directional break as the market waits for July sowing data. Rural-FMCG (DABUR) range-bound; food-inflation worry simmers but no fresh shock to yields or the INR.",
                "probability": 0.5
            },
            "downside": {
                "threshold": "Advance stalls / cumulative deficit widens past ~20-25% below LPA / IMD flags rising deficient-season odds",
                "impact": "Agri/rural complex sells off: M&M (-1.5-3%), ESCORTS (-2-4%), HEROMOTOCO/TVSMOTOR (-1.5-3%) on kharif-demand fears; fertilisers/agrochem COROMANDEL/UPL/PIIND (-2-4%). Food-inflation risk lifts bond yields and pressures the INR, hitting rural-FMCG (DABUR -1-2.5%) and capping rate-cut hopes; hydropower/agri-credit sentiment also dents.",
                "probability": 0.3
            }
        },
        "historical_analogues": [
            "Jun 2023: El Niño-driven monsoon hit Kerala ~8 days late and June rainfall ran a deep deficit -> M&M and Escorts fell ~2-3% over the following sessions on kharif-demand fears before recovering on a July catch-up.",
            "Aug 2023: driest August on record (~36% below LPA) reignited food-inflation worry -> agri-input and rural-FMCG names (Coromandel, Dabur) underperformed Nifty by ~2-4% as CPI risk lifted bond yields.",
            "Apr 2024: IMD's above-normal (106% of LPA) forecast for a La Niña year sparked a rural-recovery trade -> M&M +3% and Escorts ~+4% intraday as tractor-volume upgrades flowed through."
        ],
        "related_sectors": [
            "Agriculture & Fertilisers",
            "Automobiles (Tractors & 2-Wheelers)",
            "Rural FMCG",
            "Agrochemicals"
        ],
        "related_tickers": [
            "M&M.NS",
            "ESCORTS.NS",
            "COROMANDEL.NS",
            "UPL.NS",
            "HEROMOTOCO.NS",
            "DABUR.NS"
        ]
    },
    {
        "event_date": "2026-06-09",
        "event_time_ist": "07:00",
        "title": "China CPI, PPI & Trade Balance (May)",
        "country": "CN",
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "description": "China's May inflation and trade dump from the NBS/GACC, released pre-market IST. PPI is the single most market-moving line for India: it proxies factory-gate pricing power and global metal demand, while the import figure signals raw-material appetite. The April print surprised hot (PPI +2.8% y/y, fastest since Jul-2022; imports +25.3%), so May continuation versus a deflation relapse decides whether the Nifty Metal rally extends. Key numbers to watch: PPI y/y, CPI y/y, and whether imports stay double-digit positive — firm prints lift Tata Steel/Hindalco, soft prints pressure them via LME/SHFE metal prices.",
        "prior_value": "Apr 2026 actuals: CPI +1.2% y/y, PPI +2.8% y/y, Trade surplus $84.82bn (exports +14.1%, imports +25.3% y/y)",
        "consensus_estimate": "CPI ~+1.0% y/y, PPI ~+2.3% y/y, Trade surplus ~$90bn (exports ~+9% y/y, imports ~+15% y/y)",
        "scenarios": {
            "upside": {
                "threshold": "PPI >= +2.8% y/y AND imports >= +18% y/y (firm/reflationary)",
                "impact": "Confirms Chinese industrial restock; LME copper/aluminium and SHFE rebar firm. Nifty Metal extends: HINDALCO.NS +2.5-4%, TATASTEEL.NS +2-3.5%, VEDL.NS +3-5%, NMDC.NS +2-3%. Iron-ore/steel demand read-through also nudges JSWSTEEL.NS +1.5-2.5%. Mild INR drag from firmer commodity import bill is second-order vs the equity-price tailwind.",
                "probability": 0.3
            },
            "expected": {
                "threshold": "PPI +2.0 to +2.6% y/y, imports +10 to +18% y/y (in-line, gradual reflation holds)",
                "impact": "No regime change — metals trade with global cues, not the print. Nifty Metal +/-1%; HINDALCO.NS and TATASTEEL.NS within +/-1-1.5%, VEDL.NS/NMDC.NS muted. Market leans on LME overnight and DXY/INR rather than the data. Net neutral-to-mildly-positive for the metals basket.",
                "probability": 0.45
            },
            "downside": {
                "threshold": "PPI <= +1.5% y/y (decel/back toward deflation) OR imports < +8% y/y (demand soft)",
                "impact": "Revives China-deflation/weak-demand narrative; LME base metals and SHFE rebar sell off, dragging Indian metals. TATASTEEL.NS -2.5-4%, HINDALCO.NS -2-3.5%, VEDL.NS -3-5%, NMDC.NS -2-4%, JSWSTEEL.NS -1.5-3%. Coal/mining names (COALINDIA.NS) -1-2% on softer thermal-demand read. Risk-off can mildly firm USDINR, a small extra headwind for import-heavy metal converters.",
                "probability": 0.25
            }
        },
        "historical_analogues": [
            "Dec 13, 2024: soft China-demand cues hit base metals -> Nifty Metal slid ~3% intraday, with SAIL and NMDC down over 4% and Tata Steel over 2%, illustrating how weak China read-through transmits to the Indian metals basket (Business Standard).",
            "Sep 2024: China stimulus optimism (PBOC RRR/rate cuts) plus firmer import data -> Nifty Metal rallied ~8.5% over five sessions, Tata Steel +4% and Hindalco to a 52-week high near Rs 720 as LME copper jumped.",
            "Apr 2026 (this series' prior): hot PPI +2.8% and imports +25.3% surprise -> Nifty Metal rallied ~3% on May 27, Hindalco to Rs 1,154 high, Tata Steel +2.06%, confirming the China-PPI -> Indian-metals transmission."
        ],
        "related_sectors": [
            "Metals & Mining",
            "Steel",
            "Non-Ferrous Metals",
            "Commodities"
        ],
        "related_tickers": [
            "TATASTEEL.NS",
            "HINDALCO.NS",
            "JSWSTEEL.NS",
            "VEDL.NS",
            "NMDC.NS",
            "COALINDIA.NS"
        ]
    },
    {
        "event_date": "2026-06-10",
        "event_time_ist": "18:00",
        "title": "US CPI Inflation (May)",
        "country": "US",
        "category": "ECONOMIC_DATA",
        "importance": "HIGH",
        "description": "US May CPI (headline + core) prints at 8:30 ET / 18:00 IST — the single most market-moving global release of the week, landing exactly one week before the June 16-17 FOMC. It directly resets Fed rate-cut odds: April CPI already re-accelerated to 3.8% y/y headline / 2.8% y/y core (+0.6% m/m, hottest headline since May 2023) on a Middle-East energy spike, so a second hot print would all but kill near-term cut hopes. For Indian equities the transmission is DXY and US 10Y yields: a hot number lifts the dollar and yields, pressures INR past 96, and revives FII-outflow risk for Nifty; a cool print does the reverse. Watch headline y/y (~4.0% expected), core y/y (~2.9%), and the m/m momentum — the result is not yet known.",
        "prior_value": "Headline 3.8% y/y (+0.6% m/m), Core 2.8% y/y — April 2026 print, hottest headline since May 2023",
        "consensus_estimate": "Headline ~4.0% y/y (+0.4% m/m), Core ~2.9% y/y (+0.3% m/m)",
        "scenarios": {
            "upside": {
                "threshold": "Cool / soft surprise: headline <= 3.7% y/y OR core <= 2.7% y/y, with m/m <= +0.2%",
                "impact": "Risk-on for Indian equities. DXY and US 10Y yields fall, INR firms toward 94.5, FII-flow risk recedes and June Fed-cut odds revive. Rate-sensitives lead: Nifty/Bank Nifty +0.8-1.5%, HDFCBANK.NS / ICICIBANK.NS +1-2%, NBFCs like BAJFINANCE.NS +2-3%, autos and realty +1.5-3%. IT (INFY.NS, TCS.NS) catches a relief bid on an improved US-demand / discretionary-spend read, +1-2%.",
                "probability": 0.25
            },
            "expected": {
                "threshold": "In-line: headline 3.9-4.1% y/y, core 2.8-3.0% y/y, m/m +0.3-0.4%",
                "impact": "Sticky-but-no-shock outcome. Fed stays on hold June 16-17 as broadly priced; DXY and yields little changed, INR steady ~95.2-95.6. Nifty range-bound +/-0.5% with a modest relief tilt once tail risk clears. IT (TCS.NS, INFY.NS) flat-to-+0.5%; banks (ICICIBANK.NS) drift +/-0.5%. Stock-specific and global-cues driven rather than a macro re-rating.",
                "probability": 0.45
            },
            "downside": {
                "threshold": "Hot surprise: headline >= 4.2% y/y OR core >= 3.1% y/y, with m/m >= +0.5%",
                "impact": "Risk-off for Indian equities. Cut hopes evaporate, DXY spikes, US 10Y yields jump 8-15bps, INR weakens past 96.3 — reviving FII outflows. Nifty -1-2%, Bank Nifty -1.5-2.5%; rate-sensitive NBFCs BAJFINANCE.NS -2.5-4% and realty hit hardest. HDFCBANK.NS / ICICIBANK.NS -1.5-2.5%. IT is mixed: a weaker INR cushions margins (tailwind) but US-recession / sticky-rate fear caps INFY.NS / TCS.NS to -0.5% to +1%.",
                "probability": 0.3
            }
        },
        "historical_analogues": [
            "Sep 2024: US CPI cooled to 2.4% y/y (a 3.5-yr low) -> DXY softened, FIIs turned buyers, Nifty +1.0% and Bank Nifty +1.4% the next session on revived Fed-cut bets.",
            "Apr 2024: US CPI surprised hot at 3.5% y/y, pushing back rate-cut timing -> USDINR hit a then-record ~83.5, FIIs sold ~Rs 8,000 Cr, Nifty fell ~0.9% and rate-sensitive NBFCs dropped 2-3%.",
            "May 2026 (April print): headline jumped to 3.8% y/y vs 3.7% expected on a Middle-East energy spike -> US 10Y yields rose, DXY firmed, and Nifty's rate-sensitives (banks, realty) underperformed as June-cut odds were trimmed."
        ],
        "related_sectors": [
            "Banks & Financials",
            "IT Services",
            "NBFCs / Rate-Sensitives",
            "Realty"
        ],
        "related_tickers": [
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "INFY.NS",
            "TCS.NS",
            "BAJFINANCE.NS",
            "RELIANCE.NS"
        ]
    },
    {
        "event_date": "2026-06-10",
        "event_time_ist": "21:00",
        "title": "OPEC Monthly Oil Market Report",
        "country": "",
        "category": "COMMODITY",
        "importance": "MEDIUM",
        "description": "OPEC's monthly demand/supply outlook is the cartel's official read on 2026 world oil demand growth, OECD/non-OECD balances and member production (OPEC+ quotas) — the single biggest scheduled mover of Brent crude. With Brent already elevated near $95-97/bbl after April's Strait-of-Hormuz spike to ~$138, India (which imports ~85% of its crude, ~4.3 mb/d) is acutely exposed: every $10/bbl on Brent worsens the import bill, pressures the rupee (already ~95/USD) and widens the current account deficit (tracking ~2.1% of GDP). Watch the headline 2026 demand-growth number (last print 1.17 mb/d, cut from 1.38), any tweak to the supply/OPEC+ output path, and the Q2-26 balance — a higher demand or tighter-supply tilt is bullish crude (good for ONGC/Oil India, bad for OMCs/paints/aviation), a downgrade flips it.",
        "prior_value": "2026 world oil demand growth cut to +1.17 mb/d (from +1.38 mb/d) in the May-2026 MOMR; Brent ~$95/bbl spot, Q2-26 demand ~104.6 mb/d",
        "consensus_estimate": "2026 demand growth held roughly steady near +1.1 to +1.2 mb/d; Brent assumed in the $90-100/bbl band with supply path broadly unchanged",
        "scenarios": {
            "upside": {
                "threshold": "Hawkish for crude: 2026 demand growth revised UP toward +1.3 mb/d and/or supply path tightened (deeper OPEC+ restraint), pushing Brent above ~$100/bbl",
                "impact": "Higher crude is a tailwind for upstream producers but a headwind for the broader import-heavy market. ONGC.NS +2-4% and OIL.NS +2-5% on stronger realisations; conversely OMCs squeezed on marketing margins — BPCL.NS / IOC.NS -2-4%; crude-derivative input cost names like ASIANPAINT.NS -1.5-3%; aviation hit on fuel — INDIGO.NS -2-4%. Transmission chain: higher Brent -> larger import bill -> INR weakens past ~95/USD -> imported inflation lifts G-sec yields -> rate-sensitives (autos, NBFCs) soften; Nifty modestly heavy.",
                "probability": 0.3
            },
            "expected": {
                "threshold": "In-line: demand growth left broadly unchanged near +1.1 to +1.2 mb/d, supply path reaffirmed, Brent stable in the $90-100/bbl band",
                "impact": "Muted, already-priced reaction. Oil & gas and OMC names move <1% either way; INR steady around 94-95/USD and the 10Y yield little changed. Brent two-way risk stays headline-driven (Middle East geopolitics dominate the report). Net Nifty impact negligible; energy basket roughly flat with stock-specific noise rather than a sector trend.",
                "probability": 0.45
            },
            "downside": {
                "threshold": "Dovish for crude: 2026 demand growth cut further toward +1.0 mb/d (OECD weakness) and/or looser supply guidance, dragging Brent below ~$88/bbl",
                "impact": "Lower crude is broadly bullish for import-dependent India. OMCs gain on fatter marketing margins — BPCL.NS / IOC.NS / HINDPETRO.NS +2-4%; paints/input-cost names relieved — ASIANPAINT.NS +1.5-3%; aviation benefits — INDIGO.NS +2-4%. Upstream lags — ONGC.NS / OIL.NS -1.5-3% on softer realisations. Transmission chain: lower Brent -> smaller import bill -> INR firms toward ~93/USD -> cooler imported inflation -> G-sec yields ease -> supportive for rate-sensitives and overall Nifty risk appetite.",
                "probability": 0.25
            }
        },
        "historical_analogues": [
            "Apr 2026: Strait of Hormuz disruption sent Brent to ~$138 intraday and ~$117 avg for the month -> Nifty Energy upstream (ONGC, Oil India) outperformed while BPCL/HPCL/IOC and IndiGo fell 4-7% on margin/fuel-cost fears and INR slid past 95/USD.",
            "May 2026: OPEC cut 2026 demand growth to +1.17 mb/d (from +1.38) citing OECD weakness -> Brent eased intraday, OMC basket (BPCL/IOC) firmed ~1-2% next session on improved marketing-margin outlook while ONGC drifted lower.",
            "Mar 2020: OPEC+ price-war collapse crashed Brent toward ~$25/bbl -> Indian OMCs (BPCL/IOC/HPCL) rallied sharply on import-bill relief and inventory gains, while ONGC and Oil India sank on collapsing realisations."
        ],
        "related_sectors": [
            "Oil & Gas",
            "Oil Marketing Companies (OMCs)",
            "Aviation",
            "Paints / Chemicals"
        ],
        "related_tickers": [
            "ONGC.NS",
            "OIL.NS",
            "BPCL.NS",
            "IOC.NS",
            "ASIANPAINT.NS",
            "INDIGO.NS"
        ]
    },
    {
        "event_date": "2026-06-11",
        "event_time_ist": "18:00",
        "title": "US PPI (May) + Initial Jobless Claims",
        "country": "US",
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "description": "US producer prices for May plus weekly initial jobless claims, released together at 8:30 ET (6:00 PM IST), one day after May CPI. PPI is the pipeline-inflation cross-check that confirms or contradicts the CPI signal heading into the 16-17 June FOMC; with April PPI having spiked to +6.0% y/y (+1.4% m/m) on the Iran-driven energy shock, the key question is whether May's ~20% Brent pullback finally cooled producer prices. Matters for Indian equities because a hot print lifts the DXY and US 10y yield, pressures the already record-weak rupee (~₹95-96/$), and squeezes IT and rate-sensitive banks; rising jobless claims would soften that. Watch PPI final demand y/y (prior 6.0%), core PPI y/y (prior 4.4%) and claims (prior ~225k).",
        "prior_value": "PPI final demand +6.0% y/y (+1.4% m/m), core PPI +4.4% y/y (Apr 2026); Initial jobless claims 225k (week ended 30 May 2026, 4-wk avg ~208k)",
        "consensus_estimate": "PPI +5.4% y/y (+0.3% m/m), core PPI +4.2% y/y; Initial jobless claims ~218k",
        "scenarios": {
            "upside": {
                "threshold": "PPI >= 5.7% y/y (clear upside surprise vs 5.4% consensus) OR m/m >= +0.6% AND/OR claims < 205k — hot, sticky pipeline inflation",
                "impact": "Confirms CPI hawkishness into the FOMC: DXY firms, US 10y yield pushes higher, rupee skids toward fresh lows past ₹96/$. IT exporters get a one-day FX tailwind but are capped by US-recession demand fear — TCS.NS/INFY.NS roughly flat to +0.5%. Rate-sensitive financials and autos sell off on imported-inflation/higher-for-longer fear — HDFCBANK.NS/ICICIBANK.NS -0.8% to -1.8%, MARUTI.NS -1% to -2%. Net Nifty -0.4% to -1.0%.",
                "probability": 0.3
            },
            "expected": {
                "threshold": "PPI 5.2-5.6% y/y (m/m +0.2% to +0.5%), core ~4.2% AND claims 205-225k — moderating off the April spike, in line with consensus",
                "impact": "Markets read the May Brent pullback feeding through; relief that pipeline inflation is rolling over without a labour-market crack. DXY/yields little changed to softer, rupee stabilises near ₹95/$. Mildly risk-positive for Indian equities — banks HDFCBANK.NS/ICICIBANK.NS +0.2% to +0.7%, IT TCS.NS/INFY.NS flat to +0.5%. Nifty -0.2% to +0.4%, low-conviction drift ahead of the FOMC.",
                "probability": 0.5
            },
            "downside": {
                "threshold": "PPI <= 4.8% y/y (m/m <= 0.0%) AND/OR claims > 240k — sharp disinflation plus labour softening",
                "impact": "Revives a 2026 rate-cut bid: DXY and US 10y yield fall, rupee firms toward ₹94.5/$, FII risk appetite improves. Rate-sensitives rally hardest — HDFCBANK.NS/ICICIBANK.NS +1.0% to +2.0%, RELIANCE.NS +0.8% to +1.5%; IT mixed as FX tailwind fades but US-demand hope helps INFY.NS +0.3% to +1.0%. Nifty +0.5% to +1.2%. A claims spike alone (growth-scare) would mute the equity upside.",
                "probability": 0.2
            }
        },
        "historical_analogues": [
            "Mar 2022 PPI surged to +11.2% y/y on the post-Ukraine energy spike -> US 10y yield jumped ~15bps, DXY firmed and Nifty fell ~1.2% the next session as imported-inflation fear hit banks and autos",
            "Aug 2023 PPI ticked up to +1.6% y/y vs +0.8% expected (hot) -> DXY rose, USD/INR weakened past 83 and Bank Nifty slid ~0.9% the following day while IT held flat on the FX cushion",
            "Nov 2024 PPI cooled to +3.0% y/y, reinforcing a soft CPI -> US yields eased, rupee steadied and Bank Nifty rallied ~1.3% next session on revived rate-cut hopes"
        ],
        "related_sectors": [
            "IT Services",
            "Banking & Financials",
            "Automobiles",
            "Oil & Gas"
        ],
        "related_tickers": [
            "TCS.NS",
            "INFY.NS",
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "MARUTI.NS",
            "RELIANCE.NS"
        ]
    },
    {
        "event_date": "2026-06-12",
        "event_time_ist": "17:30",
        "title": "India CPI Inflation (May)",
        "country": "IN",
        "category": "ECONOMIC_DATA",
        "importance": "HIGH",
        "description": "May retail inflation (CPI), released by MoSPI at ~17:30 IST, is the week's defining India macro print. It re-sets the inflation-glidepath narrative after the RBI's June MPC held the repo rate at 5.25% (neutral stance) and raised its FY27 CPI projection to 5.1%, and it shapes August-MPC pricing, where the rate-hike case has been quietly building on food and rupee pressures. With April headline at 3.48% y/y (still sub-4% target) but food CFPI accelerating to 4.20% and core near 4.4%, the key tells are: (1) headline relative to the ~3.6% consensus, (2) the food/CFPI trajectory, and (3) whether sticky core eases. A soft print keeps the dovish glidepath intact and is bullish rate-sensitives; a hot print revives the hike narrative and pressures yields and high-duration sectors. The actual print is not yet known — this is a forward-looking preview.",
        "prior_value": "3.48% y/y (Apr 2026 headline CPI; food CFPI 4.20% y/y, core ~4.4% y/y)",
        "consensus_estimate": "~3.6% y/y headline (food CFPI seen ~4.3-4.5% y/y)",
        "scenarios": {
            "upside": {
                "threshold": "Soft print: headline < 3.4% y/y with food/CFPI cooling",
                "impact": "Dovish glidepath reinforced, August-cut odds rebuild, 10Y G-sec yield eases 5-8bps. Bullish rate-sensitives: Bank Nifty +0.8% to +1.5% led by HDFCBANK.NS, ICICIBANK.NS, SBIN.NS; NBFCs BAJFINANCE.NS +1.5% to +2.5% (lower funding-cost narrative); realty (DLF.NS) and autos (M&M.NS, MARUTI.NS) +1% to +2% on cheaper-EMI demand. INR steady-to-firmer as real rates stay attractive.",
                "probability": 0.3
            },
            "expected": {
                "threshold": "In-line: headline 3.4% to <3.9% y/y, food broadly as expected",
                "impact": "Status-quo reaction - confirms RBI's neutral hold without forcing a new bias. Bank Nifty range-bound -0.3% to +0.5%; HDFCBANK.NS / ICICIBANK.NS flat-to-mildly-positive, BAJFINANCE.NS muted. 10Y yield within +/-3bps, INR stable. Market pivots to global cues (US CPI, Brent, DXY) for the next leg; little durable single-stock alpha from the print itself.",
                "probability": 0.45
            },
            "downside": {
                "threshold": "Hot print: headline >= 3.9% y/y (at/near target) on food spike or sticky core",
                "impact": "Hike narrative for H2 FY27 revives, August-cut odds collapse, 10Y G-sec yield jumps 6-10bps and INR weakens. Bearish rate-sensitives: Bank Nifty -1.0% to -2.0%, NBFCs hardest hit - BAJFINANCE.NS -2% to -3.5% on higher-for-longer funding costs; realty DLF.NS and rate-sensitive autos M&M.NS -1.5% to -3% on EMI/demand drag. Defensives (FMCG, IT) relatively outperform.",
                "probability": 0.25
            }
        },
        "historical_analogues": [
            "Feb 2025 CPI cooled to 3.61% y/y (well below the 4% target) -> Bank Nifty rallied ~1.4% the next session as Apr-2025 cut odds firmed and 10Y G-sec yields eased.",
            "Oct 2024 CPI spiked to 6.21% y/y (above the 6% upper band) on a food/vegetable surge -> Nifty Bank fell ~1.2% and the 10Y G-sec yield rose ~7bps as rate-cut hopes were pushed out.",
            "Apr 2026 CPI ticked up to 3.48% y/y with food CFPI at 4.20% (still sub-target) -> rate-sensitives held firm and Bank Nifty traded flat-to-positive as the sub-4% headline kept the RBI hold benign."
        ],
        "related_sectors": [
            "Banks",
            "NBFCs / Financials",
            "Realty",
            "Auto"
        ],
        "related_tickers": [
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "SBIN.NS",
            "BAJFINANCE.NS",
            "DLF.NS",
            "M&M.NS"
        ]
    },
    {
        "event_date": "2026-06-12",
        "event_time_ist": "17:30",
        "title": "India Industrial Production / IIP (April)",
        "country": "IN",
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "description": "The Index of Industrial Production (IIP) measures year-on-year momentum in factory output across manufacturing, mining, electricity and capital goods, released by MoSPI alongside the CPI print. It matters for Indian equities because it is the cleanest read on the real-economy capex/industrial cycle: a strong print validates the order-book strength of capital-goods and infrastructure names (L&T, Siemens, ABB, BHEL) and underpins industrial/PSU cyclicals, while a weak print signals demand slowdown and pressures the same cohort plus auto and metals. The numbers to watch are headline IIP y/y, the manufacturing sub-index (the heaviest weight), and capital-goods growth as the leading capex tell. Note the series now runs on the revamped 2022-23 base year (the first release under it carried a broader 463-item-group basket), so y/y comparability against the old 2011-12 series is loose. This entry is forward-looking — the figures below are priors and Street estimates, not the actual result.",
        "prior_value": "+4.1% y/y (March 2026; manufacturing +4.3%, mining +5.5%, capital goods a standout +14.6%, headline index 173.2 vs 166.3 a year earlier on the prevailing series)",
        "consensus_estimate": "+4.6% y/y (Street range ~4.0-5.2%; manufacturing seen ~5.5-6.0%, capital goods staying double-digit)",
        "scenarios": {
            "upside": {
                "threshold": ">= 5.5% y/y (manufacturing > 6.5%, capital goods accelerating double-digit)",
                "impact": "Confirms the capex upcycle is broadening. Capital-goods and infra names lead: LT.NS +1.5-3%, SIEMENS.NS / ABB.NS +2-4%, BHEL.NS +3-5% on PSU-capex re-rating. Transmission: stronger real-economy output validates order-book visibility and FY27 earnings, drawing FII/DII flows into industrials and lifting the Nifty cap-goods/PSU baskets; auto ancillaries and metals (TATASTEEL.NS) ride the demand-pull +1-2%. Nifty broadly +0.3-0.6% with leadership rotating to cyclicals over defensives.",
                "probability": 0.25
            },
            "expected": {
                "threshold": "in-line 4.0-5.2% y/y (manufacturing ~5.5-6%, mining and capital goods steady)",
                "impact": "A steady-as-she-goes print is largely discounted; muted, stock-specific reaction. Capital-goods names (LT.NS, SIEMENS.NS, ABB.NS) drift +/-0.5-1% with no decisive sector rotation, and the index keys off the simultaneous CPI print and global cues (Brent, DXY) rather than IIP. Bond yields and INR barely move since IIP alone does not shift the RBI's neutral stance. Net Nifty impact roughly flat, +/-0.2%.",
                "probability": 0.5
            },
            "downside": {
                "threshold": "< 4.0% y/y (manufacturing < 5%, broad-based deceleration / capital goods stalling)",
                "impact": "Signals industrial-cycle cooling and softens the capex-revival narrative. Cyclicals sell off: BHEL.NS -3-5%, LT.NS -1.5-3%, SIEMENS.NS / ABB.NS -2-4%; metals and defence-capex read-through (TATASTEEL.NS, BEL.NS) -1-2.5% on weaker domestic-demand signal. Transmission: a soft real-economy print revives growth-slowdown worries, firming the rate-cut bet (10y G-sec yields ease 2-4 bps) and rotating money out of industrials into rate-sensitive/defensive bond proxies and FMCG. Nifty -0.3-0.6%, with the cap-goods/PSU basket the clear underperformer.",
                "probability": 0.25
            }
        },
        "historical_analogues": [
            "Mar 2026 IIP slowed to +4.1% y/y (a multi-month low) but capital goods stayed a standout at +14.6% -> capital-goods names held firm and L&T finished roughly flat-to-marginally-green next session as resilient capex offset the headline deceleration.",
            "Mar 2024 IIP printed +4.9% y/y with capital goods +6.1% and basic-metals strength -> the cap-goods/PSU cohort (BHEL, BEL, L&T) saw relative strength over the following sessions as the capex-revival trade gained conviction.",
            "May 2024 IIP surprised to the upside near +6% on manufacturing strength -> Nifty PSU/cap-goods basket (BHEL, BEL, L&T) outperformed +1.5-2.5% over the following sessions as the capex trade gained conviction."
        ],
        "related_sectors": [
            "Capital Goods",
            "Industrials",
            "Infrastructure",
            "Metals"
        ],
        "related_tickers": [
            "LT.NS",
            "SIEMENS.NS",
            "ABB.NS",
            "BHEL.NS",
            "TATASTEEL.NS",
            "BEL.NS"
        ]
    },
    {
        "event_date": "2026-06-12",
        "event_time_ist": "17:00",
        "title": "India Forex Reserves (Weekly)",
        "country": "IN",
        "category": "ECONOMIC_DATA",
        "importance": "LOW",
        "description": "RBI's weekly snapshot of India's foreign exchange reserves (for the week ended June 5), released every Friday at ~17:00 IST. Normally a low-impact, informational print, but the size and direction of the weekly change reveal how aggressively the RBI is selling dollars to defend a record-weak rupee (~95.2/USD) amid the West Asia conflict and elevated oil prices. Watch the headline total versus the prior $682.3bn and the week-on-week delta: a large drawdown (>$5bn) signals heavy intervention and rupee stress, pressuring import-heavy names (OMCs, autos); a build signals easing pressure. The gold-revaluation component also swings the headline regardless of FX flows.",
        "prior_value": "$682.3bn (week ended May 29, 2026; +$0.9bn w/w after a $7.51bn slide the prior week; down from the Feb-2026 record of $728.49bn)",
        "consensus_estimate": "~$680-684bn (roughly flat to modestly lower w/w; market focus on whether RBI dollar-selling pace exceeds ~$3-4bn)",
        "scenarios": {
            "upside": {
                "threshold": "Reserves BUILD by >$4bn to >$686bn (signals easing rupee pressure / lighter RBI intervention, helped by gold revaluation)",
                "impact": "Risk-positive for INR and import-heavy names. A visible build eases fears of a disorderly rupee slide: USD/INR can firm 20-40 paise toward 94.8-95.0. OMCs benefit from cheaper dollar crude payables — BPCL.NS, IOC.NS, HINDPETRO.NS +0.8-1.8%; import-cost-sensitive autos MARUTI.NS +0.5-1.2%. Lower INR-vulnerability premium supports rate-sensitives and broad Nifty +0.2-0.5%. Mechanism: lighter intervention -> stable/stronger INR -> lower imported-inflation and input-cost fears.",
                "probability": 0.25
            },
            "expected": {
                "threshold": "Roughly flat to modestly lower, ~$679-684bn (small w/w move, gold-driven noise, intervention broadly priced in)",
                "impact": "Largely a non-event for single stocks; INR and equities trade on the RBI policy outcome, DXY and crude instead. USD/INR holds the 95.0-95.7 range; OMCs and MARUTI.NS move <0.5% on the print alone. Bank Nifty and Nifty drift +/-0.3% with no reserves-specific transmission. The market reads 'flat' as RBI smoothing volatility without burning the buffer — a status-quo signal.",
                "probability": 0.55
            },
            "downside": {
                "threshold": "Sharp DRAWDOWN >$6bn to <$676bn (heavy dollar-selling to defend the rupee; reserves near a 1-year+ low)",
                "impact": "Risk-off for INR-vulnerable names. A large drop confirms aggressive intervention and a rupee under stress: USD/INR can push toward 95.7-96.2, near fresh record lows. Import-heavy OMCs face costlier dollar crude payables and marketing-margin risk — BPCL.NS, IOC.NS, HINDPETRO.NS -1.0-2.5%; MARUTI.NS -0.6-1.5% on imported-component cost. Falling import-cover headlines lift the INR-risk premium, pressuring rate-sensitive financials and high-beta — Bank Nifty -0.4-0.9%, Nifty -0.3-0.6%. Mechanism: reserve burn -> weaker/less-defensible INR -> imported inflation + external-buffer worry -> sell import-cost-exposed sectors.",
                "probability": 0.2
            }
        },
        "historical_analogues": [
            "Jan 16, 2026: reserves jumped >$14bn to ~$701bn (gold revaluation + inflows) -> USD/INR firmed ~25 paise and BPCL.NS/IOC.NS rose ~1% next session as rupee-vulnerability fears eased.",
            "Week ended May 22, 2026: reserves slid $7.51bn to $681.38bn (heavy intervention + $4.5bn gold drop) -> USD/INR hit successive record lows near 96.2 and HINDPETRO.NS/MARUTI.NS underperformed ~1-1.5% on import-cost worry.",
            "Feb 27, 2026: reserves peaked at a record $728.49bn before the West Asia conflict triggered a multi-month drawdown of ~$45bn -> rupee weakened from ~87 toward 95+ and OMCs derated as crude payables ballooned."
        ],
        "related_sectors": [
            "Oil Marketing / Energy",
            "Automobiles",
            "Banks / Financials",
            "Currency-sensitive importers"
        ],
        "related_tickers": [
            "BPCL.NS",
            "IOC.NS",
            "HINDPETRO.NS",
            "MARUTI.NS",
            "RELIANCE.NS",
            "HDFCBANK.NS"
        ]
    },
    {
        "event_date": "2026-06-12",
        "event_time_ist": "19:30",
        "title": "US Michigan Consumer Sentiment (June, prelim)",
        "country": "US",
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "description": "The preliminary University of Michigan Consumer Sentiment survey for June, released 10:00 ET (19:30 IST) Friday, with the market's real focus on the embedded 1-year and 5-year inflation-expectations components. After the May final collapsed to a record-low 44.8 with 1-yr expectations climbing to 4.8% on the 2026 Iran/Strait-of-Hormuz fuel shock, any further rise in expectations would harden the 'higher-for-longer' Fed narrative, support DXY and US yields, and pressure USD/INR (a stronger dollar = weaker rupee) into the weekend. For Indian stocks the spillover lands the following Monday: a firmer dollar weighs on FII flows and rate-sensitives, while a weaker INR is a mild tailwind for IT/pharma exporters. Watch the 1-yr inflation-expectations number above all (prior 4.8%) and the headline index (prior 44.8). This is a forward-looking preview; no June result is yet known.",
        "prior_value": "Headline 44.8 (May final, record low); 1-yr inflation expectations 4.8%, 5-yr 3.9%",
        "consensus_estimate": "Headline ~46.0 (June prelim); 1-yr inflation expectations ~4.7-4.8%, 5-yr ~3.9%",
        "scenarios": {
            "upside": {
                "threshold": "1-yr inflation expectations cool to <= 4.5% (and/or headline rebounds > 48)",
                "impact": "Eases the higher-for-longer Fed fear -> US yields and DXY soften from ~99, the rupee firms and USD/INR slips back toward 93.5 (below the 94-95 base) -> FII risk-on into Indian equities Monday. Rate-sensitives and banks lead: ICICIBANK.NS / HDFCBANK.NS +0.8-1.5%, broad Nifty +0.5-1.0%. Pharma/IT exporters lag the rally as the firmer INR trims their export tailwind.",
                "probability": 0.25
            },
            "expected": {
                "threshold": "1-yr inflation expectations in-line 4.6-4.9%, headline ~45-47",
                "impact": "Confirms sticky-but-stable expectations; muted reaction. DXY holds ~99, USD/INR steady near 94-95 -> Indian indices open Monday flat to +/-0.3%. IT (TCS.NS, INFY.NS) modestly supported by a firm dollar but capped by a soft US-discretionary-spend read; net Nifty drift within +/-0.5%.",
                "probability": 0.5
            },
            "downside": {
                "threshold": "1-yr inflation expectations jump to >= 5.0% (or 5-yr > 4.0%)",
                "impact": "De-anchoring fear -> Fed-cut hopes pushed out, US yields and DXY spike above 100 -> the rupee weakens and USD/INR rises toward 95.5-96, triggering FII outflows. Rate-sensitives and high-beta sell off: banks/financials and RELIANCE.NS -1.0-2.0%, Nifty -0.7-1.3% Monday. Partial offset: the weaker INR cushions IT exporters TCS.NS / INFY.NS (-0.3% to +0.5%, relative outperformers).",
                "probability": 0.25
            }
        },
        "historical_analogues": [
            "May 2025: UMich 1-yr inflation expectations spiked to ~7.3% (tariff shock) -> DXY firmed and the rupee weakened (USD/INR pushed above 85); Nifty IT outperformed a flat-to-weak broad market the next session",
            "Nov 2024: sentiment beat with cooling inflation expectations -> US yields eased, DXY dipped and Bank Nifty added ~1.2% the following session on renewed FII buying",
            "Apr 2026: prior-month UMich collapse to record lows amid the Iran fuel crisis -> Brent above $106 weakened the rupee (USD/INR higher) and Nifty fell ~1% the next trading day as FIIs trimmed risk"
        ],
        "related_sectors": [
            "Information Technology",
            "Banking & Financials",
            "Oil & Gas",
            "Pharmaceuticals"
        ],
        "related_tickers": [
            "TCS.NS",
            "INFY.NS",
            "ICICIBANK.NS",
            "RELIANCE.NS",
            "HDFCBANK.NS",
            "SUNPHARMA.NS"
        ]
    },
    {
        "event_date": "2026-06-15",
        "event_time_ist": "12:00",
        "title": "India WPI Inflation (May)",
        "country": "IN",
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "description": "May wholesale price inflation (released Monday 15th as the 14th is a weekend). WPI is heavily weighted toward commodities and manufacturing input costs, so it often flags margin pressure ahead of the CPI read — the April print already spiked to 8.3% y/y (from 3.88% in March), the fastest in years, on a fuel & power basket up ~24.7% and manufactured-products inflation at 4.62%, with crude petroleum surging on Brent above $100/bbl and a weak rupee (~Rs 95/USD). Elevated WPI squeezes manufacturer gross margins (FMCG, autos, cement, consumer durables) faster than firms can pass it to consumers. Watch the fuel & power and manufactured-products components and the sequential (m/m) momentum, not just the headline y/y.",
        "prior_value": "8.3% y/y (April 2026, prov.); fuel & power +24.7% y/y, manufactured products +4.62% y/y",
        "consensus_estimate": "~8.2% y/y (range 7.9-8.6%); manufactured products ~4.6% y/y, fuel & power ~22-25% y/y",
        "scenarios": {
            "upside": {
                "threshold": ">= 8.8% y/y (or manufactured products > 5.0% y/y)",
                "impact": "Hot, cost-push surprise — margin-squeeze fears intensify for input-heavy consumption names. ASIANPAINT.NS and BERGEPAINT.NS (crude-derivative inputs) -1.5% to -3%, HINDUNILVR.NS / NESTLEIND.NS -1% to -2.5% as gross-margin compression gets re-rated, MARUTI.NS / TATAMOTORS.NS -1% to -2.5% on steel/metal pass-through. Hardens RBI's hawkish-hold (repo 5.25%); 10Y G-sec yield +5-10 bps, INR pressured toward Rs 95.5+, Bank Nifty heavyweights flat-to-soft. Cement (ULTRACEMCO.NS) -1% to -2% on fuel/pet-coke cost.",
                "probability": 0.35
            },
            "expected": {
                "threshold": "in-line 7.9-8.6% y/y",
                "impact": "Print broadly matches the elevated April handle — already priced, so muted index reaction (Nifty +/-0.4%). Margin-sensitive FMCG/auto names move +/-0.75% on component mix: a softer manufactured-products read helps ASIANPAINT.NS / HINDUNILVR.NS modestly, a hot fuel read offsets it. Yields and INR little changed; RBI on-hold narrative intact. Rotation stays toward pricing-power and financials over cost-takers.",
                "probability": 0.45
            },
            "downside": {
                "threshold": "< 7.6% y/y (cooler, esp. if fuel base effect rolls over)",
                "impact": "Cooler-than-feared print eases the cost-push narrative — relief rally in margin-takers. ASIANPAINT.NS / BERGEPAINT.NS +1.5% to +3%, HINDUNILVR.NS / NESTLEIND.NS +1% to +2%, MARUTI.NS +1% to +2% on input-cost relief. 10Y yield -5-8 bps, INR firms modestly, rate-cut hopes nudge rate-sensitives (autos, NBFCs) higher; Nifty +0.4% to +0.8%.",
                "probability": 0.2
            }
        },
        "historical_analogues": [
            "April 2026 WPI spiked to 8.3% y/y (from 3.88% in March) on fuel & power +24.7% and surging crude — paint and FMCG cost-takers (Asian Paints, HUL) underperformed Nifty as gross-margin fears resurfaced.",
            "Sept 2022 was the last time WPI fuel inflation and manufactured-products inflation ran this hot before April 2026; manufacturing inflation peaked and FMCG/paints names de-rated on the input-cost squeeze before easing through 2023.",
            "May 2022 WPI hit a record ~15.9% y/y on the crude/commodity spike post-Ukraine — Asian Paints and HUL slid 2-4% intraday and the 10Y G-sec yield jumped ~8 bps as margin-compression fears gripped consumption stocks."
        ],
        "related_sectors": [
            "FMCG",
            "Automobiles",
            "Paints & Consumer Durables",
            "Cement"
        ],
        "related_tickers": [
            "ASIANPAINT.NS",
            "HINDUNILVR.NS",
            "NESTLEIND.NS",
            "MARUTI.NS",
            "TATAMOTORS.NS",
            "ULTRACEMCO.NS"
        ]
    },
    {
        "event_date": "2026-06-15",
        "event_time_ist": "16:00",
        "title": "India Merchandise Trade Balance (May)",
        "country": "IN",
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "description": "The Commerce Ministry's monthly DGFT release reports May goods exports, imports and the resulting merchandise trade deficit. It matters for Indian equities because a wider deficit pressures the current account and the rupee (already near record lows ~95.4/USD), which feeds into RBI policy room, import-cost inflation and FPI flows. With Brent crude back near $97/bbl on Gulf tensions and gold/silver imports running hot, the deficit and its oil-vs-bullion split are the key numbers to watch. This is a forward-looking schedule entry; the May result is not yet known.",
        "prior_value": "Apr 2026: merchandise deficit US$28.4bn (exports US$43.56bn, imports US$71.94bn); combined merch+services balance -US$7.81bn",
        "consensus_estimate": "Merchandise deficit ~US$27-29bn (exports ~US$42-44bn, imports ~US$70-72bn)",
        "scenarios": {
            "upside": {
                "threshold": "Deficit narrows to < US$25bn (oil/gold imports cool, exports hold > US$44bn)",
                "impact": "A smaller-than-feared deficit eases CAD/INR stress: rupee firms 0.2-0.4% toward 95.0/USD, 10Y G-Sec yield softens a few bps. OMCs benefit from cheaper crude pass-through into marketing margins — BPCL.NS and IOC.NS +1.5-3%, HINDPETRO.NS +2-4%. Import-cost-sensitive paint/aviation names like ASIANPAINT.NS +1-2%. Gems & jewellery exporters TITAN.NS +1-2% if the narrowing is export-led.",
                "probability": 0.3
            },
            "expected": {
                "threshold": "In-line deficit US$25-29bn (broadly matching April's ~US$28bn run-rate)",
                "impact": "A print near consensus is largely discounted — INR roughly flat at 95.3-95.6/USD, Nifty/Bank Nifty muted (+/-0.3%). OMCs (BPCL.NS, IOC.NS, HINDPETRO.NS) trade in a +/-1% band tracking the crude line in the data rather than the headline. Rotation stays driven by crude and global DXY; the release is a low-volatility, second-order input for index traders.",
                "probability": 0.45
            },
            "downside": {
                "threshold": "Deficit widens to > US$30bn (Brent stays elevated above ~US$97 / pushes toward US$100 lifting the oil bill + bullion imports surge)",
                "impact": "A blowout deficit pressures the rupee 0.3-0.6% weaker toward 96/USD and lifts the 10Y yield 4-7bps on CAD/imported-inflation worries. OMCs hit hardest as costly crude squeezes marketing margins/under-recoveries — BPCL.NS, IOC.NS, HINDPETRO.NS -2-4%. Rupee weakness hurts importers (paints ASIANPAINT.NS -1-2%) but cushions USD-earning IT/pharma exporters (TCS.NS, SUNPHARMA.NS +0.5-1.5% on the FX tailwind). A gold-import surge weighs on jewellers' margins — TITAN.NS -1-2%.",
                "probability": 0.25
            }
        },
        "historical_analogues": [
            "Nov 2024 print: record merchandise deficit ~US$37.8bn on a gold-import spike sent INR to then-record lows and 10Y yields up ~5bps; OMCs and jewellers underperformed Nifty by ~1.5% the next session.",
            "Apr 2026 data (released 15 May 2026): deficit ~US$28bn with crude near US$97/bbl pressured INR toward 95.7/USD and weighed on BPCL/IOC ~2%, even as a near-record export tally limited the broader index hit.",
            "Jul 2024 print: deficit narrowed to ~US$23.5bn on softer oil imports, so INR firmed ~0.3% and OMCs (BPCL, HPCL) rallied 2-3% on improved marketing-margin optics the following session."
        ],
        "related_sectors": [
            "Oil & Gas / OMCs",
            "Currency-sensitive exporters (IT & Pharma)",
            "Gems & Jewellery",
            "Paints & Aviation (import-cost sensitive)"
        ],
        "related_tickers": [
            "BPCL.NS",
            "IOC.NS",
            "HINDPETRO.NS",
            "TITAN.NS",
            "TCS.NS",
            "SUNPHARMA.NS"
        ]
    },
    {
        "event_date": "2026-06-16",
        "event_time_ist": "19:30",
        "title": "US FOMC Meeting — Day 1 (No Decision)",
        "country": "US",
        "category": "CENTRAL_BANK",
        "importance": "LOW",
        "description": "Day 1 of the two-day June FOMC meeting opens with no announcement — the rate decision and the closely watched Summary of Economic Projections (dot plot) land on Day 2 (Wed, Jun 17). With the Fed funds rate held at 3.50%-3.75% since April (an 11-1 rate vote, Gov. Miran dissenting for a 25bp cut, plus 3 members objecting to the statement's easing bias) and US CPI sticky at 3.8% y/y (April print, the hottest since May 2023), desks de-risk and position into Wednesday rather than react today. For Indian equities the direct impact is limited on the day; watch the US 10Y yield (~4.46%) and DXY (~100) drift as a tell for FII risk appetite — FIIs have been heavy net sellers (-Rs 8,776 Cr cash on Jun 5, part of ~Rs 2.3 lakh Cr of 2026 YTD outflows), so any pre-decision dollar/yield uptick can keep IT and rate-sensitives heavy into the close.",
        "prior_value": "Fed funds target 3.50%-3.75% (held Apr 29, 2026; 11-1 rate vote, Miran dissented for a cut); US 10Y ~4.46%, DXY ~100.1, US CPI 3.8% y/y (Apr)",
        "consensus_estimate": "No action on Day 1 (no decision scheduled); Day-2 (Jun 17) consensus = hold at 3.50%-3.75%, market eyes dot plot for the 2026 cut path",
        "scenarios": {
            "upside": {
                "threshold": "Pre-decision risk-on: US 10Y drifts < 4.40% and DXY softens toward 99 on dovish positioning chatter",
                "impact": "Mild relief into the close — softer yields/DXY ease FII-selling pressure. Rate-sensitives lead: HDFCBANK.NS and ICICIBANK.NS +0.3-0.7%, realty/NBFC bid (BAJFINANCE.NS +0.5-1.0%). IT exporters (TCS.NS, INFY.NS) are mixed — risk-on helps but a firmer INR trims realizations. Nifty drift +0.2-0.5%. Move is small — it is only Day 1; real repricing waits for the dot plot.",
                "probability": 0.25
            },
            "expected": {
                "threshold": "Quiet positioning day: 10Y holds 4.42-4.50%, DXY 99.5-100.5, no headlines (most likely)",
                "impact": "Negligible direct India impact — index churns in a tight band as desks square up before Wednesday. INR stable near 95.0-95.6/USD; IT (TCS.NS, INFY.NS) and banks trade on domestic flow, not the Fed today. Expect Nifty +/-0.3%, low realized vol, India VIX flat. FII cash flow stays the swing factor, not this event.",
                "probability": 0.6
            },
            "downside": {
                "threshold": "Pre-decision risk-off: 10Y spikes > 4.55% and DXY > 100.8 on hawkish-hold repricing / a hot US data surprise",
                "impact": "Higher yields + stronger dollar amplify FII outflows and pressure rate-sensitives and high-duration growth names into Wednesday. NBFCs/realty soft (BAJFINANCE.NS -0.7-1.5%), private banks ICICIBANK.NS/HDFCBANK.NS -0.4-0.9%; INR slips toward 96.3/USD pressuring importers. IT (TCS.NS, INFY.NS) gets a partial INR-depreciation cushion but tracks weaker US risk -0.3-0.8%. Nifty -0.4-0.8%.",
                "probability": 0.15
            }
        },
        "historical_analogues": [
            "Dec 2024 FOMC Day 1 was a non-event, but the Day-2 hawkish dot plot (one fewer 2025 cut) sent Nifty -1.1% and Bank Nifty -1.3% the next session as the US 10Y jumped and DXY firmed — the Day-1 positioning into it was flat.",
            "Mar 2025 two-day FOMC: Day 1 passed quietly with Nifty +/-0.2%, then a dovish hold + steady dots on Day 2 lifted Bank Nifty +1.0% and eased FII selling as the 10Y eased.",
            "Sep 2025 FOMC Day 1 saw India churn flat ahead of the meeting; the actual 25bp cut on Day 2 sparked a relief rally with Nifty +0.9% and rate-sensitives (BAJFINANCE +2%) leading — confirming Day 1 itself rarely moves the tape."
        ],
        "related_sectors": [
            "Banks & Financials",
            "IT Services",
            "NBFC & Realty",
            "Currency-sensitive Exporters"
        ],
        "related_tickers": [
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "BAJFINANCE.NS",
            "TCS.NS",
            "INFY.NS",
            "RELIANCE.NS"
        ]
    },
    {
        "event_date": "2026-06-17",
        "event_time_ist": "23:30",
        "title": "US FOMC Rate Decision + Powell Press Conference",
        "country": "US",
        "category": "CENTRAL_BANK",
        "importance": "HIGH",
        "description": "The June FOMC decision (23:30 IST, 2:00 PM EST) lands with an updated Summary of Economic Projections — the quarterly \"dot plot\" — followed by Powell's press conference (~00:00 IST). The Fed has held at 3.50%-3.75% since its contentious 8-4 April vote, with inflation pushed higher by energy prices, so the rate move itself is near-certain (~96% priced for no change); the market-moving variable is how many 2026 cuts the new dots show (December dots implied just one) and whether Powell sounds hawkish-on-hold or signals an autumn cut. The dot count and tone reset DXY, the US 10-year yield and global risk appetite, which transmits straight into FII flows, the rupee, and rate-sensitive Nifty IT and bank names. Watch: the 2026 median dot, the statement's easing-bias language, and Powell's framing of energy-driven inflation as transitory vs sticky.",
        "prior_value": "Held at 3.50%-3.75% (April 29, 2026; 8-4 vote). Dec-2025 dot plot 2026 median: 3.4% (~1 cut). Fed funds upper bound 3.75%.",
        "consensus_estimate": "Hold at 3.50%-3.75% (~96% priced). 2026 median dot expected ~3.4% (1 cut, autumn-weighted); risk of a hawkish shift to 0 cuts on energy-led inflation.",
        "scenarios": {
            "upside": {
                "threshold": "Dovish hold: 2026 dots keep 1-2 cuts AND Powell flags energy inflation as transitory / signals a September cut",
                "impact": "DXY softens 0.4-0.8% and US 10Y yield slips 8-15bps -> rupee firms and FII risk-on. Nifty +0.8-1.6% next session; rate-sensitive IT leads on cheaper US funding + buyback/discretionary-spend hopes: INFY.NS / TCS.NS +1.5-3%, banks HDFCBANK.NS / ICICIBANK.NS +1-2% on flow tailwind. Rupee gains 15-30 paise.",
                "probability": 0.3
            },
            "expected": {
                "threshold": "Hawkish-on-hold: rates unchanged at 3.50-3.75%, 2026 median dot stays ~3.4% (1 cut), Powell stresses data-dependence and energy-inflation risk",
                "impact": "Muted-to-modestly-negative; outcome largely priced so reaction hinges on tone. Nifty -0.3% to +0.4%, choppy intraday; IT (INFY.NS, TCS.NS) flat-to-soft on no fresh easing, banks (ICICIBANK.NS, HDFCBANK.NS) range-bound. Rupee +/-10 paise, 10Y G-sec yield steady. Volatility compresses into the print then fades.",
                "probability": 0.5
            },
            "downside": {
                "threshold": "Hawkish surprise: 2026 dots cut to 0 cuts / dot-plot hike risk flagged, Powell explicitly higher-for-longer on sticky energy inflation",
                "impact": "DXY rallies 0.5-1.0%, US 10Y yield jumps 12-20bps -> rupee slides toward fresh lows and FII outflows extend (FPIs already net sellers ~Rs 2.2 lakh Cr YTD 2026). Nifty -1.2-2.5%; IT hit hardest on US-demand + valuation derating (INFY.NS, TCS.NS -2.5-4.5%), private banks HDFCBANK.NS / ICICIBANK.NS -1.5-3% on outflow + yield drag, and index-heavyweight RELIANCE.NS -1.5-3% as broad FII selling hits the largest cap. Rupee weakens 25-45 paise.",
                "probability": 0.2
            }
        },
        "historical_analogues": [
            "Dec 2024 FOMC: Fed cut 25bps but 2025 dots halved to 2 cuts (hawkish cut) -> DXY surged, US 10Y spiked ~12bps, Nifty fell ~1.0% next session and Nifty IT dropped ~2% on the dollar spike.",
            "Mar 2026 FOMC: dot plot kept just one 2026 cut amid doubts over easing -> Indian investors turned cautious, Nifty traded heavy and FII selling resumed as the rupee weakened.",
            "Sep 2024 FOMC: jumbo 50bp dovish cut -> risk-on globally, Bank Nifty rallied ~1.5% and FPI flows turned positive into Indian financials the following sessions."
        ],
        "related_sectors": [
            "IT",
            "Banking & Financials",
            "Currency / Rate-sensitives",
            "FMCG"
        ],
        "related_tickers": [
            "INFY.NS",
            "TCS.NS",
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "RELIANCE.NS",
            "NIFTYBEES.NS"
        ]
    }
]
