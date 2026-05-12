<div align="center">

# Alpha Lens 📈

**Next-Gen AI-Powered Indian Stock Market Intelligence**

*Real-time quantitative trade signals driven by Google Gemini, multi-model ensemble prediction, live news analysis, and technical confirmation — built for NSE/BSE.*

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Backend-black?logo=flask)](https://flask.palletsprojects.com)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-orange?logo=google)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Multi-Model Ensemble Prediction Engine](#multi-model-ensemble-prediction-engine)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Backtesting Engine](#backtesting-engine)
- [Performance Reporting](#performance-reporting)
- [Security Notice](#security-notice)
- [Notes & Limitations](#notes--limitations)
- [Contributing](#contributing)
- [Contributors](#contributors)

---

## Overview

Alpha Lens is a real-time quant research web application built for the Indian equity market (NSE/BSE). It scrapes live financial news from top-tier Indian sources via RSS feeds, pipes each headline through Google Gemini (prompted as an elite quantitative portfolio manager), and outputs structured trade signals — complete with affected tickers, directional bias (Bullish/Bearish), confidence scores, target prices, and stop-loss levels.

What sets Alpha Lens apart is its **dual-confirmation system**: every AI-generated signal is cross-validated against real-time technical indicators (RSI, SMA, Bollinger Bands, volume analysis) before being surfaced to the user. A background worker thread continuously monitors open positions using yfinance, automatically resolving trades as winners, losers, or expired based on asymmetric risk/reward thresholds.

Starting with **v4.0**, Alpha Lens introduces a **Multi-Model Ensemble Prediction Engine** — five independent rule-based models that analyze each headline from different angles (sentiment depth, historical similarity, sector momentum, and event patterns). A signal is only emitted when the ensemble score meets a minimum threshold (>= 70) **and** at least 3 out of 5 models agree, dramatically reducing false positives.

The platform also ships with a full **backtesting engine** that replays historical news headlines against past market data to measure the AI's predictive accuracy over time, along with a **backfill utility** for reprocessing existing database entries through the updated ensemble pipeline.

---

## Key Features

- **Live Market Ticker** — Real-time price tracking for NIFTY 50, SENSEX, BANK NIFTY, and MIDCAP NIFTY via yfinance with automatic % change calculation.

- **AI-Powered News Analysis** — Fetches live headlines from Economic Times, MoneyControl, and LiveMint RSS feeds, then analyzes each through Google Gemini 2.5 Flash with a quantitative finance prompt to extract actionable trade signals.

- **Multi-Model Ensemble Prediction** — Five independent models (Sentiment Depth, Historical Similarity, Sector Momentum, Event Pattern, and a weighted ensemble aggregator) cross-validate every signal. Only predictions with high ensemble agreement are surfaced, reducing noise and false positives.

- **Technical Confirmation Layer** — Every AI signal is validated against 60-day technical indicators including RSI (14-period), SMA (20/50-day), Bollinger Band positioning, volume trends, and overall market regime detection before being accepted.

- **Fuzzy Duplicate Detection** — Incoming news headlines are compared against the 50 most recent entries using sequence-matching similarity (threshold: 75%), preventing near-duplicate articles from generating redundant signals.

- **Confidence-Gated Filtering** — Only signals meeting a minimum confidence threshold (default: 65%) are surfaced. The AI assigns realistic scores: 85+ for crystal-clear catalysts, 65–84 for strong probable signals.

- **Autonomous Price Re-evaluation** — A background yfinance worker thread monitors all active positions every 10 seconds, checking against asymmetric profit targets (+1%) and stop-losses (-2%), automatically resolving trades with time-based expiry.

- **Historical Backtesting** — Bulk-processes a CSV of past news headlines against historical candle data, evaluating AI predictions at T+24h and T+48h with configurable target (+1.5%) and stop-loss (-3.0%) thresholds.

- **Backfill Utility** — Reprocesses all existing headlines in the database through the updated ensemble engine, regenerating stock impact entries with the latest prediction pipeline.

- **Performance Reporting** — Generates terminal-based performance reports with win rate, average confidence of winners vs. losers, and breakdowns by trade status (Active, Hit Target, Stopped Out, Expired).

- **OTP Authentication** — Secure email-based passwordless login using SendGrid with 6-digit OTP codes and 10-minute expiry windows.

- **Google OAuth Sign-In** — One-click authentication via Google accounts with automatic user provisioning.

- **SQLite User Management** — Lightweight persistent user database with hashed passwords and session-based authentication.

---

## Multi-Model Ensemble Prediction Engine

Alpha Lens v4.0 introduces a sophisticated ensemble system in `prediction_models.py` that runs every headline through **five independent models** before emitting a signal:

| # | Model | Class | Description |
|---|-------|-------|-------------|
| 1 | **Sentiment Depth** | `SentimentDepthModel` | Analyzes headline sentiment intensity — keyword strength, negation detection, percentage modifiers, and graded bullish/bearish vocabulary. |
| 2 | **Historical Similarity** | `HistoricalSimilarityModel` | Compares the current headline against a cache of previously seen headlines and their outcomes, scoring based on pattern similarity. |
| 3 | **Sector Momentum** | `SectorMomentumModel` | Maps affected tickers to their sectors and evaluates sector-level momentum using a sector classification map and momentum cache. |
| 4 | **Event Pattern** | `EventPatternModel` | Detects specific market-moving event types (earnings, mergers, regulatory changes, etc.) using pattern-matched rules and assigns directional scores. |
| 5 | **Ensemble Aggregator** | `EnsemblePredictor` | Collects weighted scores from all four models, computes a final ensemble score, and applies a dual gate: **score >= 70 AND 3+ models must agree** on direction. |

This dual-gate approach ensures that only high-conviction, multi-perspective signals reach the dashboard, significantly improving signal quality over single-model approaches.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (HTML/CSS/JS)                        │
│  Live Ticker │ News Cards │ Auth UI │ Signal Dashboard          │
└───────┬───────┴──────┬───────┴─────┬─────┴──────────┬───────────┘
        │              │             │                │
        ▼              ▼             ▼                ▼
┌───────────────────────────────────────────────────────────────┐
│                    FLASK SERVER (app.py)                       │
│                                                               │
│  /api/indices   /api/news/top    /api/send-otp   /api/me     │
│  /api/news/all  /api/market_update /api/verify-otp           │
│                 /api/oauth-signin  /api/logout                │
└───────┬───────────────┬────────────────────┬──────────────────┘
        │               │                    │
  ┌─────▼─────┐  ┌──────▼──────┐   ┌────────▼────────┐
  │  yfinance  │  │  RSS Feeds  │   │   SQLite DBs    │
  │  Worker    │  │  + Gemini   │   │ (users, news)   │
  │  Thread    │  │  + Ensemble │   └─────────────────┘
  └────────────┘  │  Models     │
                  └─────────────┘
        │               │
        ▼               ▼
   Live NSE/BSE    AI Trade Signals
   Price Data      + Multi-Model Confirmation
                   + Technical Confirmation
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+, Flask |
| AI Model | Google Gemini 2.5 Flash (with key rotation) |
| Ensemble Engine | Custom multi-model prediction (Sentiment, Historical, Sector, Event) |
| Technical Analysis | Custom RSI, SMA, Bollinger Bands, Volume Analysis |
| Market Data | yfinance (NSE/BSE live + historical) |
| News Sources | RSS — Economic Times, MoneyControl, LiveMint |
| Auth & Email | SendGrid (OTP), Google OAuth 2.0 |
| Database | SQLite3 (users.db, news_cache.db) |
| Frontend | HTML5, CSS3, JavaScript (vanilla) |

---

## Project Structure

```
Alpha_Lens/
├── backend/                  # Backend application files
│   ├── app.py                # Main Flask server — routes, AI news engine, yfinance worker
│   ├── prediction_models.py  # Multi-model ensemble engine (v4.0) — 5 independent models
│   ├── backtest.py           # Historical backtesting engine — replays news vs. candle data
│   ├── backfill_stocks.py    # Backfill utility — reprocesses existing DB headlines via ensemble
│   ├── technical_analysis.py # RSI, SMA, Bollinger Bands, volume analysis, market regime
│   ├── performance_report.py # Terminal-based performance reporting and win-rate analysis
│   ├── database.py           # User auth module — OTP, OAuth, SQLite session management
│   ├── news_cache.db         # SQLite DB for cached news and AI analysis results
│   ├── users.db              # SQLite DB for user accounts and sessions
│   └── venv/                 # Python virtual environment
├── frontend/                 # Frontend application files
│   └── index.html            # Main frontend dashboard (Alpha Lens | Next-Gen Macro AI)
├── scratch/                  # Development & debugging utilities
├── .env                      # Environment variables (API keys)
├── .gitignore                # Ignored files (DBs, cache, logs, venv)
└── README.md                 # Project documentation
```

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- A [NewsAPI](https://newsapi.org/) key (used in legacy/prototype mode)
- A [Google Gemini](https://ai.google.dev/) API key (one or more for key rotation)
- A [SendGrid](https://sendgrid.com/) API key with a verified sender identity
- A Google OAuth 2.0 Client ID (for Google sign-in)

### Installation

```bash
# Clone the repository
git clone https://github.com/KIRITO-899/Alpha_Lens.git
cd Alpha_Lens

# Install dependencies
pip install flask requests google-genai yfinance sendgrid feedparser pytz
```

---

## Configuration

### 1. Gemini API Keys (`app.py` and `backtest.py`)

Replace the placeholder API keys in the `API_KEYS` list with your own Google Gemini keys. Multiple keys enable automatic rotation to avoid rate limits.

```python
API_KEYS = [
    "your_gemini_api_key_1",
    "your_gemini_api_key_2",
]
```

### 2. SendGrid (`database.py`)

Replace the SendGrid API key and update the verified sender email address.

```python
SENDGRID_API_KEY = 'your_sendgrid_api_key'
# Update from_email to your verified SendGrid sender
```

### 3. Google OAuth (`index.html`)

Update the Google OAuth Client ID in the frontend HTML file for Google sign-in functionality.

---

## Usage

### Running the App

```bash
python app.py
```

This starts the Flask server along with two background worker threads:

- **AI News Engine** — Continuously scrapes RSS feeds, analyzes headlines with Gemini, runs them through the multi-model ensemble predictor, applies technical confirmation, and stores results in `news_cache.db`. Fuzzy duplicate detection prevents near-identical headlines from generating redundant signals.
- **yfinance Price Worker** — Monitors all active trade positions every 10 seconds, checking if targets or stop-losses have been hit.

Open your browser and navigate to `http://127.0.0.1:5000`.

### Running the Backtester

```bash
python backtest.py
```

The backtesting engine reads from `news_dataset.csv` (columns: `Datetime`, `Headline`) and evaluates AI predictions against real historical candle data with the following parameters:

- **Target**: +1.5% profit
- **Stop-Loss**: -3.0%
- **Evaluation Windows**: T+24h and T+48h after news publication
- **Minimum Confidence**: 65%

Sample output includes a full statistics report with total signals analyzed, win/loss breakdown, hit rates by conviction level, and average P&L.

### Running the Backfill Utility

```bash
python backfill_stocks.py
```

Reprocesses all existing news headlines in the database through the updated (relaxed) ensemble engine, generating fresh `stock_impact` entries using the latest prediction pipeline. Run this once after upgrading to v4.0 to retroactively apply ensemble scoring to historical data.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serves the main dashboard |
| GET | `/api/indices` | Live NIFTY 50, SENSEX, BANK NIFTY, MIDCAP NIFTY prices |
| GET | `/api/news/top` | Fetch top-rated AI-analyzed news signals |
| GET | `/api/news/all` | Fetch all analyzed news with full details |
| GET | `/api/market_update` | Re-evaluate live prices for active positions |
| POST | `/api/send-otp` | Send OTP email to user for authentication |
| POST | `/api/verify-otp` | Verify OTP code and create/login user session |
| POST | `/api/oauth-signin` | Sign in via Google OAuth token |
| GET | `/api/me` | Get current authenticated session user |
| POST | `/api/logout` | Destroy session and log out |

---

## Backtesting Engine

The backtester (`backtest.py`) is a standalone module that replays historical headlines through the same AI + technical analysis pipeline used in the live app. For each headline it:

1. Queries Gemini for a structured trade signal (ticker, direction, confidence, reasoning).
2. Fetches historical technical indicators (RSI, SMA, Bollinger position) at the time the news was published.
3. Applies a trade filter combining AI confidence and technical agreement.
4. Scans subsequent 1-minute and daily candles to determine if the target (+1.5%) or stop-loss (-3.0%) was hit within 24–48 hours.
5. Aggregates results into a comprehensive statistics report.

The system uses asymmetric risk/reward thresholds — a wider stop-loss gives trades breathing room while maintaining a favorable target.

---

## Performance Reporting

The `performance_report.py` module connects to `news_cache.db` and generates real-time performance metrics:

- Total news articles processed and unique stock signals generated
- Breakdown by status: Active View, Hit Target, Stopped Out, Expired
- Win rate calculated on resolved trades only (excluding active and expired)
- Average confidence comparison: winning trades vs. losing trades
- Color-coded terminal output for quick visual assessment

---

## Security Notice

> ⚠️ **Important**: The current codebase contains API keys directly in source files. Before any public or production deployment, migrate all secrets to environment variables.

Create a `.env` file in the project root:

```bash
export GEMINI_API_KEY_1=your_key
export GEMINI_API_KEY_2=your_key
export SENDGRID_API_KEY=your_key
export GOOGLE_OAUTH_CLIENT_ID=your_client_id
export FLASK_SECRET_KEY=your_secret_key
```

Add `.env` to your `.gitignore` (already configured) and update the source files to read from `os.environ`.

---

## Notes & Limitations

- **Market Hours** — yfinance returns the last available closing price outside of NSE/BSE trading hours (9:15 AM – 3:30 PM IST). Live signals are most accurate during active market sessions.
- **RSS Feed Rate Limits** — The news engine scrapes from free RSS feeds which may occasionally return cached or slightly delayed headlines.
- **Gemini API Quotas** — The system implements automatic API key rotation across multiple keys to handle rate limits. If all keys are exhausted, it will retry after a cooldown period.
- **Backtesting Trade Rules** — 1.5% profit target, 3.0% stop-loss, evaluated at T+24h and T+48h windows after news publication.
- **Technical Analysis** — Uses 60-day lookback for indicator calculation. RSI (14-period), SMA (20/50-day), Bollinger Bands (20-day, 2σ), and volume trend analysis.
- **Ensemble Gating** — The multi-model ensemble requires a score >= 70 and agreement from at least 3 out of 5 models. This reduces signal volume but improves overall accuracy.

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## Contributors

<a href="https://github.com/KIRITO-899"><img src="https://github.com/KIRITO-899.png" width="60px" alt="KIRITO-899" /></a>
<a href="https://github.com/RohanVellanki"><img src="https://github.com/RohanVellanki.png" width="60px" alt="RohanVellanki" /></a>
<a href="https://github.com/Sumant-varanasi"><img src="https://github.com/Sumant-varanasi.png" width="60px" alt="Sumant-varanasi" /></a>

---

<div align="center">

Built with ❤️ for the Indian equity market

</div>
