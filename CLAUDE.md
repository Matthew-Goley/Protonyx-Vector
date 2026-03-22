# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Vector** is a PyQt6 desktop portfolio analytics app for stock investors. It tracks positions, fetches market data via Yahoo Finance (yfinance), and displays analytics (trend direction, volatility, sector allocation) in a dark/light themed UI. Data is persisted locally in `~/Vector/data/` as JSON files.

## Setup & Running

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

No build step, test suite, or linter is configured.

## Architecture

### Module Responsibilities

| Module | Role |
|---|---|
| `main.py` | Entry point — creates `QApplication` and `VectorMainWindow` |
| `vector/app.py` | All UI classes: main window, pages, dialogs, cards |
| `vector/analytics.py` | Portfolio math: trend slope, volatility, insight text generation |
| `vector/market.py` | yfinance wrapper with TTL caching per ticker |
| `vector/storage.py` | Read/write for all four JSON files in `~/Vector/data/` |
| `vector/widgets.py` | Custom `QWidget` subclasses: sparkline, pie chart, arrow indicator, spinner, etc. |
| `vector/constants.py` | File paths, default settings values, direction/volatility thresholds |

### Data Flow

1. `VectorMainWindow` owns `StorageManager`, `MarketDataService`, and all settings/state.
2. On startup: load JSON state → show `OnboardingPage` (first run) or `MainShell` (returning).
3. `MainShell` hosts a sidebar + `QStackedWidget` with `DashboardPage`, `ProfilePage`, `SettingsPage`.
4. `DashboardPage.refresh_data()` calls `MarketDataService.build_histories()` → passes history map to `analytics.compute_portfolio_analytics()` → renders widgets.
5. A `QTimer` drives auto-refresh at the interval set in `SettingsPage` (1 min / 5 min / 15 min / manual).

### Analytics Engine (`analytics.py`)

- **Direction**: 6-month linear regression slope expressed as annualized percent. Thresholds: Strong ≥18%, Steady ≥5%, Neutral ±5%, Weak ≤-5%, Depreciating ≤-18%.
- **Volatility**: Annualized std-dev of daily returns, scaled to a 1–100 score; configurable lookback (3mo/6mo/1y).
- **Insights**: `_direction_insight`, `_volatility_insight`, `_diversification_insight` return rich-text HTML strings with data-quality warnings when history is sparse.

### Cache Strategy (`market.py`)

`MarketDataService` caches per-ticker snapshots and price history in `price_cache.json`. Cache TTL matches the user's refresh interval setting. "Manual only" mode skips automatic re-fetches entirely.

### Storage Layout

All files live under `~/Vector/data/`:
- `positions.json` — list of position objects (`ticker`, `shares`, `equity`, `sector`, `name`, `price`, `added_at`)
- `settings.json` — theme, currency, refresh interval, direction thresholds, volatility config
- `app_state.json` — `onboarding_complete` flag, `first_launch_date`
- `price_cache.json` — per-ticker snapshot + history with UTC timestamps

### Assets

`assets/vector_full.png` and `assets/vector_taskbar.png` are loaded at startup; the app falls back to a procedurally generated placeholder if they are missing.
