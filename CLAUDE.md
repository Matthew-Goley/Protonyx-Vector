# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Vector** is a PyQt6 desktop portfolio analytics app for stock investors. It tracks positions, fetches market data via Yahoo Finance (yfinance), and displays analytics (trend direction, volatility, sector allocation, Sharpe ratio, beta, dividends) in a customisable dark/light themed dashboard. Data is persisted locally in `%LOCALAPPDATA%/Protonyx/Vector/` (falls back to `~/Vector/data/`) as JSON files.

Current version: **0.3.6**

## Setup & Running

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

No build step, test suite, or linter is configured.

## Building (Nuitka)

```bash
python -m nuitka --standalone --windows-console-mode=disable --enable-plugin=pyqt6 --output-filename="Vector-v0.3.6.exe" --include-data-dir=assets=assets main.py
```

- `--include-data-dir=assets=assets` copies the entire `assets/` folder next to the exe
- `resource_path()` automatically resolves assets correctly in all three environments: dev, PyInstaller, and Nuitka standalone (see `vector/paths.py`)

## Architecture

### Module Responsibilities

| Module | Role |
|---|---|
| `main.py` | Entry point — calls `vector.app.main()` |
| `vector/app.py` | Thin shell: `DARK_STYLESHEET`, `LIGHT_STYLESHEET`, `MainShell`, `VectorMainWindow`, `main()` — all page classes live in `vector/pages/` |
| `vector/pages/dashboard.py` | `DashboardPage`, `DashboardGrid`, `WidgetPickerDialog`, grid constants (`_UNIT`, `_GAP`, `_CELL`, `_CONTENT_W`) |
| `vector/pages/lens_page.py` | `VectorLensPage`, `_GraphCard` (Monte Carlo), `_PieCard` (diversification pie) |
| `vector/pages/onboarding.py` | `OnboardingPage`, `PositionDialog`, `PositionCard` |
| `vector/pages/profile.py` | `ProfilePage` |
| `vector/pages/settings.py` | `SettingsPage`, `_AccordionSection`, `_AnimatedChevron`, `QDoubleSpinBoxCompat` |
| `vector/analytics.py` | Portfolio math: trend slope, volatility, Sharpe ratio, beta, insight HTML generation |
| `vector/store.py` | `DataStore` — single source of truth: positions, settings, app state, market data, layout; replaces `storage.py` |
| `vector/market.py` | Legacy `MarketDataService`; superseded by `DataStore` but may still be referenced |
| `vector/storage.py` | Legacy `StorageManager`; superseded by `DataStore` |
| `vector/lens_engine.py` | `generate_lens()` — computes portfolio state, selects templates, returns 6-tuple |
| `vector/lens_templates.py` | `_TEMPLATES` dict and `_COLORS` dict (extracted from `lens_engine.py`) |
| `vector/monte_carlo.py` | `run_projection()`, `build_historical_curve()` — GBM Monte Carlo simulation |
| `vector/widget_base.py` | `VectorWidget` — base `QFrame` for all dashboard widgets; handles edit-mode drag, context menu |
| `vector/widget_registry.py` | `discover_widgets()` / `get_widget_class()` — registry of all concrete widget types |
| `vector/widget_types/` | 8 concrete widget implementations + `LensDisplay` (see below) |
| `vector/widgets.py` | Shared UI primitives: `CardFrame`, `GradientBorderFrame`, `GradientLine`, `BlurrableStack`, `DimOverlay`, `EmptyState`, `LoadingButton` |
| `vector/constants.py` | File paths, TTL constants, default settings values, threshold maps |
| `vector/paths.py` | `resource_path()` (PyInstaller + Nuitka-aware asset lookup), `user_data_dir()`, `user_file()` |

### Pages subpackage (`vector/pages/`)

All page-level QWidget classes live here. `vector/app.py` imports from this subpackage — do not put new page classes directly in `app.py`.

- `_CONTENT_W = 1090` is defined in `pages/dashboard.py` and imported by `pages/lens_page.py` and `pages/settings.py` for consistent fixed-width scroll layout.
- All three scrollable pages (Dashboard, Lens, Settings) use `setWidgetResizable(False)` + `container.setFixedWidth(_CONTENT_W)` so content width is stable on window resize and the scrollbar sits at the window edge.

### Widget Types (`vector/widget_types/`)

| Class | Widget |
|---|---|
| `TotalEquityWidget` | Total portfolio value with 5-day change |
| `PortfolioVectorWidget` | Direction arrow + slope % |
| `PortfolioVolatilityWidget` | Volatility score gauge |
| `PortfolioDiversificationWidget` | Sector allocation pie |
| `PortfolioBetaWidget` | Portfolio beta vs benchmark |
| `SharpeRatioWidget` | Annualised Sharpe ratio |
| `PositionsListWidget` | Scrollable positions table |
| `DividendCalendarWidget` | Upcoming dividend dates |

### Vector Lens (`vector/widget_types/lens.py`)

`LensDisplay` is a reusable QFrame (not a VectorWidget) that renders the "Lens Brief" readout with typewriter animation and gradient-highlighted text. It is a **permanent fixture** on the dashboard (cannot be removed or repositioned) and also appears on the dedicated Vector Lens page. The dashboard instance includes a "Vector Lens ›" button that navigates to the full Lens page.

### Adding a New Widget

1. Create `vector/widget_types/<name>.py` with a class subclassing `VectorWidget`
2. Set `NAME`, `DESCRIPTION`, `DEFAULT_ROWSPAN`, `DEFAULT_COLSPAN` class attributes
3. Implement `__init__(self, window=None, parent=None)` — call `super().__init__()` first
4. Override `refresh(self)` to update the display when data changes
5. Register it in `vector/widget_registry.py` by importing and adding to `_WIDGETS`
6. `window` arg gives access to `window.store`, `window.positions`, `window.settings`

### Startup & Splash Screen

`main()` in `vector/app.py` follows this exact sequence:

1. `QApplication` is created and the taskbar icon is set.
2. `assets/splashboard.png` is loaded and displayed immediately as a `QSplashScreen` (700×400 px, centred on the primary screen, always-on-top) — this is the **first thing the user sees**.
3. `app.processEvents()` forces the OS to paint the splash before any heavy work begins.
4. `VectorMainWindow()` is constructed (loads data, builds UI) while the splash remains visible.
5. The splash is shown for a **minimum of 2 seconds** total. If construction finishes in under 2 s, a `QTimer` waits out the remainder. If it takes longer, the splash closes immediately after.
6. `splash.finish(window)` closes the splash and `window.show()` reveals the main window.

### Data Flow

1. `VectorMainWindow` owns `DataStore`, all settings/state, and the `QTimer` for auto-refresh.
2. On startup: load JSON state → show `OnboardingPage` (first run) or `MainShell` (returning).
3. `MainShell` hosts a sidebar + `QStackedWidget` with `DashboardPage`, `VectorLensPage`, `ProfilePage`, `SettingsPage`.
4. `DashboardPage` has a permanent `LensDisplay` at the top, followed by a free-form grid of `VectorWidget` instances; grid layout is loaded from / saved to `dashboard_layout.json`.
5. `DashboardPage.update_dashboard()` calls `compute_portfolio_analytics()` → refreshes the lens and calls `widget.refresh()` on each placed widget.
6. Edit mode (toolbar button) enables drag-to-reposition and right-click delete on grid widgets (the lens is not affected).
7. A `QTimer` drives auto-refresh at the interval set in `SettingsPage` (1 min / 5 min / 15 min / manual).

### Analytics Engine (`analytics.py`)

- **Direction**: 6-month linear regression slope (annualised %). Thresholds (configurable): Strong ≥18%, Steady ≥5%, Neutral ±5%, Depreciating ≤-18%, Weak ≤-5%.
- **Volatility**: Annualised std-dev of daily returns scaled to 1–100; configurable lookback (3mo/6mo/1y).
- **Sharpe ratio**: Annualised, using a 4.5% risk-free rate, from `portfolio_daily_returns()`.
- **Beta**: Portfolio covariance / benchmark variance via `portfolio_beta()`.
- **Insights**: `_direction_insight`, `_volatility_insight`, `_diversification_insight` return rich-text HTML with data-quality warnings when history is sparse.

### Lens Engine (`lens_engine.py` + `lens_templates.py`)

`generate_lens(positions, store, settings)` returns a **7-tuple**: `(text, color, recommended_tickers, deposit_amount, underweight_sector, action_type, caution_score)`.

- `text` — two plain-English sentences covering risk and next-deposit guidance (observational, not directive)
- `color` — hex color reflecting portfolio state (from `_COLORS` in `lens_templates.py`)
- `recommended_tickers` — list of tickers suggested for the next deposit (used by Monte Carlo Graph B)
- `deposit_amount` — dollar amount to bring the underweight sector to equal weight (always non-zero)
- `underweight_sector` — name of the recommended sector
- `action_type` — one of `"buy"`, `"sell"`, `"rebalance"`, `"hold"`

Template sentence banks (`_TEMPLATES`) and state color map (`_COLORS`) live in `vector/lens_templates.py`; `lens_engine.py` imports them from there.

**Action priority (15 steps, first match wins):**
1. Single position
2. Steep downtrend (per-stock, configurable threshold, default ≤ −20% annualised)
3. Excessive single-stock volatility (configurable, default > 45% annualised vol AND > 15% weight)
4. Winner concentration drift (weight > 30% AND slope > +15% annualised)
5. Index fund awareness (any INDEX_ETF > 30% weight)
6. High portfolio beta (configurable threshold, default > 1.3)
7. Sector over-concentration (configurable, default > 50%)
8. Single-stock concentration (configurable, default > 35%, non-index)
9. High-vol downtrend / weak downtrend / depreciating trend
10. High-vol uptrend / strong momentum
11. Negative Sharpe
12. Low diversification (< 3 sectors)
13. Dead weight (weight < 2% AND slope ≤ +2%)
14. Underrepresented sector (1 stock, < 10% weight)
15. Unrealized loss / low yield / neutral-diversified / hold fallback

**Signal thresholds** are configurable via Settings → Lens Signal Thresholds and stored in `settings.json` under `lens_signals`.

`INDEX_ETFS` (frozenset, 25 tickers), `LOW_BETA_BY_SECTOR` (dict), `SECTOR_SUGGESTIONS` (dict) live in `constants.py`.

`LensDisplay.refresh()` in `widget_types/lens.py` handles all tuple lengths (6, 5, 4, 3, 2) for backwards compatibility.

### Monte Carlo (Lens page)

`_GraphCard` in `pages/lens_page.py` renders GBM projections. Key notes:
- Both Graph A (without lens) and Graph B (with lens) pass `total_equity` as `current_value` to `run_projection` so historical curves normalise to the same base.
- `new_total` (portfolio + deposit) is used only to compute post-deposit weight proportions for Graph B.
- Projections display percentage change relative to current equity, not raw dollar values.
- matplotlib `FigureCanvasQTAgg` captures wheel events — fixed with `self._canvas.wheelEvent = lambda event: event.ignore()` so scrolling works when the mouse is over a chart.
- Monte Carlo parameters (projection period, simulation count) are configurable via Settings → Monte Carlo and stored under `monte_carlo` in `settings.json`. Mapping constants: `MONTE_CARLO_HORIZON_DAYS`, `MONTE_CARLO_SIMULATIONS` in `constants.py`.
- Between the projection graphs and the pie charts, two insight cards are rendered side-by-side: `_CautionCard` (left, 1:2 ratio) shows a semi-circular arc gauge with the portfolio caution score (1–99); `_MCContextCard` (right) shows a plain-English template sentence explaining what the narrower projection fan means. Both are populated in `VectorLensPage._update_insights()`.

### Settings Page (`pages/settings.py`)

Six accordion sections plus two static sections:

| Section | Type | Contents |
|---|---|---|
| General | Static card | Theme, currency, date format |
| Data & Refresh | Accordion | Auto-refresh interval, clear cache, reset all data |
| Portfolio Direction Thresholds | Accordion | Strong/steady/neutral/weak/depreciating slope cutoffs |
| Volatility | Accordion | Lookback period, low/high vol cutoffs |
| Lens Signal Thresholds | Accordion | Stock/sector concentration %, steep downtrend %, high beta threshold, vol threshold % |
| Monte Carlo | Accordion | Projection period combo, simulation count combo |
| Positions | Static card | Add/remove positions |
| About | Static card | Version, brand, credits |

**Accordion fix**: `_AccordionSection._measure()` always remeasures (no cache), forces `layout().activate()` before `sizeHint()`, and calls `parent.adjustSize()` in `_on_finished()` so the scroll area recomputes its range when multiple accordions are open simultaneously.

**LoadingButton gradient**: `LoadingButton.start_loading()` sets `setProperty('loading', True)` + `style().unpolish/polish()` before `setEnabled(False)`. The CSS rule `QPushButton[accent='true'][loading='true']:disabled` in both stylesheets preserves the gradient during loading state.

### Onboarding (`pages/onboarding.py`)

`OnboardingPage` keyboard shortcut: pressing **A** opens the Add Position dialog (calls `open_add_modal()`).

### DataStore (`store.py`)

`DataStore` is the authoritative data layer — use it for all reads and writes, not `StorageManager` or `MarketDataService`.

**Market data TTLs (stored in `market_data.json`):**

| Data | TTL |
|---|---|
| Quote / intraday history | Matches `refresh_interval` setting |
| 1mo+ daily history | 60 min |
| Meta (name, sector, industry…) | 24 h |
| Dividends | 24 h |
| Earnings calendar | 24 h |

**Key methods:**

- `validate_ticker(ticker)` — live fetch, no cache; used during onboarding
- `get_snapshot(ticker, refresh_interval)` → `{ticker, price, sector, name}`
- `get_history(ticker, period, refresh_interval)` → `list[float]` (close prices)
- `get_ohlcv(ticker, period, refresh_interval)` → `{dates, opens, highs, lows, closes, volumes}`
- `get_dividends(ticker)` → `list[{date, amount}]`
- `get_earnings(ticker)` → `list[{date, eps_estimate_avg, …}]`
- `get_quote(ticker)` / `get_meta(ticker)` — cached accessors (no network call)
- `build_histories(tickers, refresh_interval, lookback)` → history map for analytics
- `build_history_map(tickers, periods, refresh_interval)` → general-purpose close map
- `load_layout()` / `save_layout(layout)` — dashboard widget layout
- `clear_market_cache()` / `reset_all_data()` — wipe helpers

### Storage Layout

All files live under `%LOCALAPPDATA%/Protonyx/Vector/` (Windows) or `~/Vector/data/` (fallback):

| File | Contents |
|---|---|
| `positions.json` | List of position objects: `ticker`, `shares`, `equity`, `sector`, `name`, `price`, `added_at` |
| `settings.json` | Theme, currency, date_format, refresh_interval, direction_thresholds, volatility, lens_signals, monte_carlo |
| `app_state.json` | `onboarding_complete`, `first_launch_date` |
| `market_data.json` | Per-ticker: quote, meta, history, history_ohlcv, history_intraday, dividends, earnings — with UTC timestamps |
| `dashboard_layout.json` | Ordered list of `{class_name, row, col, rowspan, colspan}` for the dashboard grid |
| `price_cache.json` | Legacy cache — superseded by `market_data.json`; kept for backwards compat |

### Assets

All assets live in `assets/` and are loaded via `resource_path()`:

| File | Purpose |
|---|---|
| `assets/vector_full.png` | Full logo used in the UI |
| `assets/vector_taskbar.png` | Taskbar / window icon |
| `assets/splashboard.png` | Splash screen image (1400×800 source, displayed at 700×400) |

`resource_path()` in `vector/paths.py` handles three environments:
- **Dev**: resolves relative to the repo root (`Path(__file__).parent.parent`)
- **PyInstaller**: resolves from `sys._MEIPASS`
- **Nuitka standalone**: resolves from `Path(sys.executable).parent` (detected via `sys.frozen`)

The app falls back to a procedurally generated placeholder logo if `vector_full.png` or `vector_taskbar.png` are missing. The splash screen is silently skipped if `splashboard.png` is missing (pixmap will be null).
