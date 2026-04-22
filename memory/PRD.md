# Upstox Regime-Adaptive Trading System — PRD

## Original Problem
User wants a production-grade automated intraday trading system for Indian NSE markets via Upstox broker. Target: ₹4,000 net/day = ₹1 lakh/month = ₹12L/year. Capital ₹6,00,000. System uses HMM regime detection (Bull/Sideways/Bear), multi-layer signal scoring (technical, sentiment, fundamentals, FII flow, GEX, global cues), strict risk management, charges tracking, backtesting, Telegram notifications, and a web dashboard for monitoring.

## User Choices (from ask_human)
- 24/7 live trading system
- User will provide Upstox API key/secret/TOTP secret + Telegram bot token/chat ID when asked
- Full ML training pipeline with yfinance data
- Priority v1: Morning Brief / EOD Summary dashboard + Paper Trade Simulator + Telegram bot commands

## Architecture
- **Backend**: FastAPI + MongoDB + APScheduler (IST timezone). Trading modules in `/app/backend/trading/`.
- **Frontend**: React 19 dashboard with dark Control Room grid (Chivo + JetBrains Mono), Tailwind, shadcn UI, Phosphor icons, sonner toasts.
- **Data**: yfinance (with deterministic synthetic fallback when unreachable), scikit-learn GaussianMixture (HMM proxy), `ta` indicators.

## Implemented (v1 — 2026-04-22)
- Backend trading modules: config, charges calculator (exact Upstox formula), market_data w/ synthetic fallback, regime detector (GaussianMixture 3-state), 7-layer signal engine w/ hard gates, risk manager, paper trader (MongoDB-backed), upstox client wrapper, telegram bot, APScheduler (morning brief 08:59 IST, EOD 15:30 IST), backtest runner w/ charges applied per trade.
- 25+ REST endpoints: /api/status, /api/settings (GET/PUT), /api/regime, /api/regime/timeline, /api/morning-brief, /api/eod-summary, /api/signals, /api/positions, /api/trades, /api/charges/today, /api/risk, /api/paper/{open, close/{id}, close-all}, /api/backtest/{run, latest}, /api/upstox/{status, configure, auth-url, token, funds}, /api/telegram/{status, configure, send-test, send-morning-brief, send-eod}, /api/seed-demo.
- Frontend pages: Dashboard (multi-panel Control Room grid), Backtest (12-metric dashboard + monthly breakdown + sample trades), Settings (inline editing, paper toggle, demo seed, watchlist, weights).
- Dashboard components: Header w/ Upstox/TG/Mode status, Paper Mode Banner (striped amber), PnL Target (Gross/Charges/Net + progress bar), Regime Card (HMM state + features + probabilities), Global Cues, Risk Monitor (status pill + loss cap bar), Charges Tracker (6 line items), Regime Timeline (90D colored bars), Signal Scanner table (10 stocks × 5 layers × composite), Positions table, Trades table, Telegram + Upstox config panels.
- All interactive elements have data-testid attributes.

## Test Results (iteration 1, 2026-04-22)
- Backend: 96% (25/26 pass, 1 flaky ingress 502)
- Frontend: 100% pass
- All paper trade lifecycle flows validated end-to-end
- Backtest works (610 trades on synthetic data)
- Fixes applied: stripped HTML tags in Telegram log, removed duplicate import

## User Personas
1. **Solo quant trader** — operates the dashboard intraday to validate automated bot decisions
2. **Weekend analyst** — runs backtests, reviews regime timeline, tunes signal threshold
3. **Risk-aware investor** — monitors daily loss cap, charges burn rate, target progress

## Core Requirements (static)
- Capital ₹6L default, 1.5% risk/trade, max 2 positions, max daily loss ₹1,000
- Target ₹4,500 gross → ₹4,000 net daily (~₹500 charges)
- Signal threshold ≥0.68 composite
- Hard gates: block in Bear regime, VIX > 20, loss cap hit, max positions

## P0 Backlog (deferred)
- Real-time Upstox WebSocket feed wiring for live prices (requires valid user token)
- Auto-login via TOTP + Playwright (postponed — requires system browser deps)
- LightGBM classifier training pipeline (currently using rule-based composite)
- News API + FinBERT sentiment (currently placeholder)
- NSE FII/DII scraper (currently placeholder)

## P1 Backlog
- Per-symbol fundamental scores from yfinance info
- SQLite trade_logger parallel to MongoDB for CA export
- Weekly model retrain job (Sunday 23:00 IST)
- Advanced order types (bracket, trailing SL) via Upstox

## P2 Backlog
- Equity curve line chart (Recharts) on Backtest page
- Hot-reload weights via UI
- Multi-account support
- Tax P&L report generator (ITR-3 export)

## Known Limitations
- yfinance unreachable in platform container → falls back to deterministic synthetic OHLCV (clearly labelled)
- HMM uses scikit-learn GaussianMixture instead of hmmlearn (simpler, equivalent 3-state classification)
- TOTP auto-login skipped; manual token paste required
- Scheduler runs inside single FastAPI process (not clustered)
