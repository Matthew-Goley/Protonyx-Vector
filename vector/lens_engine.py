"""
Lens engine for Vector.

Generates exactly two plain-English sentences describing the portfolio's
current state. Output is purely observational — no investment advice or
directives are produced.

The engine:
  1. Computes per-ticker and portfolio-level metrics (direction, volatility,
     Sharpe, beta, HHI, concentration, dividend yield).
  2. Selects an action from a 14-step priority list (first match wins).
  3. Picks a template pair deterministically (same portfolio + same day →
     same template) and formats it with the computed context.
  4. Persists a structured snapshot to lens_snapshot.json for future analysis.
  5. Returns the canonical 5-tuple consumed by LensDisplay and lens_page.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from .lens_templates import _COLORS, _TEMPLATES

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sector → representative tickers
# ---------------------------------------------------------------------------

_PREFERRED_SECTORS: list[str] = [
    'Technology', 'Healthcare', 'Consumer Defensive', 'Financial Services',
    'Financials', 'Industrials', 'Energy', 'Consumer Cyclical',
    'Communication Services', 'Utilities', 'Real Estate', 'Basic Materials',
]

_SECTOR_TICKERS: dict[str, list[str]] = {
    'Technology':             ['AAPL', 'MSFT', 'NVDA', 'GOOG', 'META'],
    'Healthcare':             ['UNH', 'JNJ', 'PFE', 'ABBV', 'LLY'],
    'Consumer Defensive':     ['PG', 'KO', 'PEP', 'WMT', 'COST'],
    'Financial Services':     ['JPM', 'V', 'BRK-B', 'MA', 'BAC'],
    'Financials':             ['JPM', 'V', 'BRK-B', 'MA', 'BAC'],
    'Industrials':            ['CAT', 'HON', 'UNP', 'GE', 'RTX'],
    'Energy':                 ['XOM', 'CVX', 'COP', 'SLB', 'EOG'],
    'Consumer Cyclical':      ['AMZN', 'TSLA', 'HD', 'NKE', 'MCD'],
    'Communication Services': ['GOOG', 'META', 'DIS', 'NFLX', 'T'],
    'Utilities':              ['NEE', 'DUK', 'SO', 'D', 'AEP'],
    'Real Estate':            ['AMT', 'PLD', 'CCI', 'O', 'SPG'],
    'Basic Materials':        ['LIN', 'APD', 'SHW', 'ECL', 'NEM'],
}

# Sectors most commonly associated with dividend income
_DIVIDEND_SECTORS: list[str] = [
    'Utilities', 'Consumer Defensive', 'Real Estate',
    'Financial Services', 'Financials',
]

# ---------------------------------------------------------------------------
# Sector complement notes — observational, educational, non-prescriptive.
# Describe what each sector IS and how it historically relates to others.
# ---------------------------------------------------------------------------

_SECTOR_COMPLEMENT_NOTES: dict[str, str] = {
    'Technology': (
        'Technology is a high-growth, rate-sensitive sector — it has historically'
        ' outperformed in low-rate environments and shown steeper drawdowns'
        ' during rising-rate or risk-off cycles.'
    ),
    'Healthcare': (
        'Healthcare has historically shown lower correlation to broad market'
        ' swings than most growth sectors, often maintaining value during'
        ' Technology and cyclical drawdowns.'
    ),
    'Consumer Defensive': (
        'Consumer Defensive stocks — staples, household goods, groceries — have'
        ' historically shown more stable earnings through economic downturns,'
        ' with lower drawdowns than cyclical sectors.'
    ),
    'Utilities': (
        'Utilities are income-generating and rate-sensitive, historically moving'
        ' differently from growth sectors and providing a yield component'
        ' that pure equity portfolios typically lack.'
    ),
    'Financial Services': (
        'Financial Services performance is closely linked to interest rate cycles'
        ' and credit conditions, following different drivers than technology earnings.'
    ),
    'Financials': (
        'Financial sector performance is closely tied to interest rate cycles'
        ' and credit conditions, diverging from technology earnings during'
        ' most rate environment shifts.'
    ),
    'Energy': (
        'Energy is driven by global commodity price cycles — oil, gas, refining'
        ' margins — which have historically shown low correlation to domestic'
        ' technology and services earnings.'
    ),
    'Consumer Cyclical': (
        'Consumer Cyclical stocks are tied to discretionary spending and consumer'
        ' confidence, following different cycles from technology earnings'
        ' and less sensitive to rate changes.'
    ),
    'Industrials': (
        'Industrials tend to track broader economic output cycles, often diverging'
        ' from Technology during late-cycle and early-contraction periods.'
    ),
    'Communication Services': (
        'Communication Services blends high-growth digital names with legacy'
        ' media and telecom components, offering mixed correlation characteristics'
        ' relative to pure Technology exposure.'
    ),
    'Real Estate': (
        'Real Estate Investment Trusts are income-generating and rate-sensitive,'
        ' following property market and credit cycles that are distinct from'
        ' equity growth trends.'
    ),
    'Basic Materials': (
        'Basic Materials are driven by global commodity demand and supply cycles,'
        ' historically showing low correlation to domestic technology'
        ' and services sectors.'
    ),
}

_SECTOR_COMPLEMENT_FALLBACK = (
    'This sector represents a different segment of the economy and has'
    ' historically followed different price cycles from the current holdings.'
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sector_ticker_hint(sector: str, held_tickers: set[str], n: int = 3) -> str:
    """Return '(TICK1, TICK2, TICK3)' for *sector*, excluding already-held tickers."""
    candidates = _SECTOR_TICKERS.get(sector, [])
    picks = [t for t in candidates if t not in held_tickers][:n]
    if not picks:
        picks = candidates[:n]
    return '(' + ', '.join(picks) + ')' if picks else ''


def _sector_ticker_list(sector: str, held_tickers: set[str], n: int = 3) -> list[str]:
    """Return ticker suggestions for *sector*, excluding already-held tickers."""
    candidates = _SECTOR_TICKERS.get(sector, [])
    picks = [t for t in candidates if t not in held_tickers][:n]
    if not picks:
        picks = candidates[:n]
    return picks


def _best_underweight_sector(
    held_sectors: set[str],
    sector_weights: dict[str, float],
) -> str:
    """Return the best sector to diversify into next."""
    for s in _PREFERRED_SECTORS:
        if s not in held_sectors:
            return s
    if sector_weights:
        return min(sector_weights, key=sector_weights.__getitem__)
    return 'a different sector'


def _calc_deposit(
    target_sector: str,
    known_sectors: set[str],
    sector_weights: dict[str, float],
    total_equity: float,
) -> float:
    """
    Return the dollar amount needed to bring *target_sector* to equal weight
    with all other sectors.  Formula: D = (E − n·eq) / (n − 1)
    """
    n = len(known_sectors) + (1 if target_sector not in known_sectors else 0)
    n = max(n, 2)
    current_eq = sector_weights.get(target_sector, 0.0)
    return max((total_equity - n * current_eq) / (n - 1), 0.0)


def _pick_template(action: str, positions: list[dict]) -> int:
    """
    Deterministic index — stable for the same portfolio on the same calendar day,
    changes when holdings or the action key changes.
    """
    today = date.today().isoformat()
    key = action + '|' + ','.join(sorted(p['ticker'] for p in positions)) + '|' + today
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return h % len(_TEMPLATES[action])


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------


def _save_snapshot(snapshot: dict) -> None:
    """
    Append *snapshot* to ``lens_snapshot.json``, capping at LENS_HISTORY_MAX
    entries (FIFO).  Silently swallows all I/O errors.
    """
    from .constants import LENS_HISTORY_MAX, LENS_SNAPSHOT_FILE
    from .paths import user_file

    path = user_file(LENS_SNAPSHOT_FILE)
    try:
        history: list[dict] = []
        if path.exists():
            with open(path, 'r', encoding='utf-8') as fh:
                history = json.load(fh)
        history.append(snapshot)
        if len(history) > LENS_HISTORY_MAX:
            history = history[-LENS_HISTORY_MAX:]
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(history, fh, indent=2)
    except Exception:  # noqa: BLE001
        _log.debug('lens_snapshot write failed — non-critical', exc_info=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_lens_history() -> list[dict]:
    """
    Return the rolling snapshot list from ``lens_snapshot.json``.
    Returns an empty list if the file is missing or unreadable.
    """
    from .constants import LENS_SNAPSHOT_FILE
    from .paths import user_file

    path = user_file(LENS_SNAPSHOT_FILE)
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as fh:
                return json.load(fh)
    except Exception:  # noqa: BLE001
        _log.debug('lens_snapshot read failed', exc_info=True)
    return []


def generate_lens(
    positions: list[dict[str, Any]],
    store: Any,
    settings: dict[str, Any],
) -> tuple[str, str, list[str], float, str]:
    """
    Analyse the portfolio and return a 5-tuple:

    - ``text``                — two plain-English observational sentences
    - ``color``               — hex color reflecting portfolio state
    - ``recommended_tickers`` — tickers relevant to the selected action
    - ``deposit_amount``      — dollar amount for Monte Carlo Graph B (0.0 if N/A)
    - ``underweight_sector``  — sector used for deposit math ('' if N/A)
    """
    from .analytics import (
        annualized_volatility,
        classify_direction,
        classify_volatility,
        linear_regression_slope_percent,
        portfolio_beta,
        portfolio_daily_returns,
        score_volatility,
        sharpe_ratio,
    )
    from .constants import VOLATILITY_LOOKBACK_PERIODS

    # ── Empty portfolio ───────────────────────────────────────────────────
    if not positions:
        return (
            'Add your first position to see Lens analytics tailored to your'
            ' actual holdings. Go to Settings and add a stock or ETF ticker'
            ' to get started.',
            '#8d98af', [], 0.0, '',
        )

    # ── Settings ──────────────────────────────────────────────────────────
    refresh_interval: str = settings.get('refresh_interval', '5 min')
    thresholds: dict[str, float] = settings.get('direction_thresholds', {
        'strong': 0.08, 'steady': 0.02,
        'neutral_low': -0.02, 'neutral_high': 0.02,
        'depreciating': -0.08,
    })
    vol_settings: dict[str, Any] = settings.get('volatility', {})
    lookback: str = vol_settings.get('lookback', '6 months')
    period: str = VOLATILITY_LOOKBACK_PERIODS.get(lookback, '6mo')
    low_cut: int = int(vol_settings.get('low_cutoff', 30))
    high_cut: int = int(vol_settings.get('high_cutoff', 60))

    total_equity: float = sum(p.get('equity', 0.0) for p in positions) or 1.0

    # ── Per-ticker metrics ────────────────────────────────────────────────
    slopes: dict[str, float] = {}
    vols: dict[str, float] = {}
    equities: dict[str, float] = {}
    histories: dict[str, list[float]] = {}

    for pos in positions:
        t: str = pos['ticker']
        eq: float = pos.get('equity', 0.0)
        equities[t] = eq
        try:
            h = store.get_history(t, '6mo', refresh_interval)
            histories[t] = h or []
            slopes[t] = linear_regression_slope_percent(histories[t])
        except Exception:  # noqa: BLE001
            slopes[t] = 0.0
            histories[t] = []
        try:
            vh = store.get_history(t, period, refresh_interval)
            vols[t] = annualized_volatility(vh or [])
        except Exception:  # noqa: BLE001
            vols[t] = 0.0

    weighted_slope: float = sum(
        slopes[t] * equities[t] / total_equity for t in slopes
    )
    weighted_vol: float = sum(
        vols[t] * equities[t] / total_equity for t in vols
    )

    dir_label: str
    dir_label, _dir_color, _ = classify_direction(weighted_slope, thresholds)
    vol_score: int = score_volatility(weighted_vol)
    vol_label: str
    vol_label, _ = classify_volatility(vol_score, low_cut, high_cut)

    # ── Sector map ────────────────────────────────────────────────────────
    sector_weights: dict[str, float] = {}
    for p in positions:
        s: str = p.get('sector') or 'Unknown'
        sector_weights[s] = sector_weights.get(s, 0.0) + p.get('equity', 0.0)

    held_sectors: set[str] = set(sector_weights.keys())
    known_sectors: set[str] = {s for s in held_sectors if s != 'Unknown'}
    sector_count: int = len(known_sectors) or len(held_sectors)

    sorted_sectors = sorted(
        sector_weights, key=sector_weights.__getitem__, reverse=True
    )
    top_sector: str = sorted_sectors[0] if sorted_sectors else 'Unknown'
    top_sector_pct: float = sector_weights.get(top_sector, 0.0) / total_equity * 100
    second_sector: str = sorted_sectors[1] if len(sorted_sectors) >= 2 else top_sector

    # ── Concentration metrics ─────────────────────────────────────────────
    stock_pcts: dict[str, float] = {
        t: eq / total_equity * 100 for t, eq in equities.items()
    }
    max_single_stock_pct: float = max(stock_pcts.values()) if stock_pcts else 0.0
    most_concentrated_ticker: str = (
        max(stock_pcts, key=stock_pcts.__getitem__) if stock_pcts else ''
    )
    most_concentrated_pct: float = stock_pcts.get(most_concentrated_ticker, 0.0)

    concentrated_stock: str | None = None
    concentrated_stock_pct: float = 0.0
    for t, pct in stock_pcts.items():
        if pct > 40.0:
            concentrated_stock = t
            concentrated_stock_pct = pct
            break

    hhi: float = sum(
        (eq / total_equity * 100) ** 2 for eq in sector_weights.values()
    )

    # ── Performance extremes ──────────────────────────────────────────────
    most_volatile_ticker: str = (
        max(vols, key=vols.__getitem__)
        if vols else positions[0]['ticker']
    )
    most_volatile_vol: float = vols.get(most_volatile_ticker, 0.0) * 100

    worst_ticker: str = (
        min(slopes, key=slopes.__getitem__)
        if slopes else positions[0]['ticker']
    )
    worst_slope: float = slopes.get(worst_ticker, 0.0)

    best_ticker: str = (
        max(slopes, key=slopes.__getitem__)
        if slopes else positions[0]['ticker']
    )
    best_slope: float = slopes.get(best_ticker, 0.0)

    # ── Sharpe ratio ──────────────────────────────────────────────────────
    closes_map: dict[str, list[float]] = {t: h for t, h in histories.items() if h}
    daily_rets: list[float] = []
    try:
        daily_rets = portfolio_daily_returns(positions, closes_map)
    except Exception:  # noqa: BLE001
        pass

    sharpe_val: float | None = None
    if len(daily_rets) >= 10:
        try:
            sharpe_val = sharpe_ratio(daily_rets)
        except Exception:  # noqa: BLE001
            pass

    # ── Portfolio beta ────────────────────────────────────────────────────
    beta_val: float | None = None
    if len(daily_rets) >= 10:
        try:
            spy_hist = store.get_history('SPY', '6mo', refresh_interval) or []
            if len(spy_hist) > 1:
                spy_returns: list[float] = [
                    (spy_hist[i] - spy_hist[i - 1]) / spy_hist[i - 1]
                    for i in range(1, len(spy_hist))
                ]
                if len(spy_returns) >= 10:
                    beta_val = portfolio_beta(daily_rets, spy_returns)
        except Exception:  # noqa: BLE001
            pass

    # ── Dividend yield ────────────────────────────────────────────────────
    div_yield_val: float | None = None
    try:
        weighted_yield = 0.0
        has_any_yield = False
        for pos in positions:
            t = pos['ticker']
            eq = pos.get('equity', 0.0)
            quote = store.get_quote(t) or {}
            y = (
                quote.get('dividendYield')
                or quote.get('trailingAnnualDividendYield')
                or 0.0
            )
            if y:
                weighted_yield += float(y) * eq
                has_any_yield = True
        div_yield_val = (weighted_yield / total_equity * 100) if has_any_yield else 0.0
    except Exception:  # noqa: BLE001
        pass

    has_dividend_positions: bool = (
        div_yield_val is not None and div_yield_val > 0.1
    )

    # ── Sector / underweight helpers ──────────────────────────────────────
    held_tickers: set[str] = {p['ticker'] for p in positions}

    underweight: str = _best_underweight_sector(held_sectors, sector_weights)
    # Ensure underweight != top_sector
    if underweight == top_sector and len(sector_weights) > 1:
        underweight = second_sector

    underweight_tickers_str: str = _sector_ticker_hint(underweight, held_tickers)
    uw_ticker_list: list[str] = _sector_ticker_list(underweight, held_tickers, 3)
    underweight_ticker1: str = uw_ticker_list[0] if len(uw_ticker_list) > 0 else underweight
    underweight_ticker2: str = uw_ticker_list[1] if len(uw_ticker_list) > 1 else underweight
    underweight_ticker3: str = uw_ticker_list[2] if len(uw_ticker_list) > 2 else underweight

    dividend_sector: str = next(
        (s for s in _DIVIDEND_SECTORS if s not in held_sectors),
        _DIVIDEND_SECTORS[0],
    )
    div_ticker_list: list[str] = _sector_ticker_list(dividend_sector, held_tickers, 2)
    div_ticker1: str = div_ticker_list[0] if div_ticker_list else dividend_sector
    div_ticker2: str = div_ticker_list[1] if len(div_ticker_list) > 1 else div_ticker1

    # ── Sector complement notes ───────────────────────────────────────────
    underweight_sector_note: str = _SECTOR_COMPLEMENT_NOTES.get(
        underweight, _SECTOR_COMPLEMENT_FALLBACK
    )
    dividend_sector_note: str = _SECTOR_COMPLEMENT_NOTES.get(
        dividend_sector, _SECTOR_COMPLEMENT_FALLBACK
    )

    # ── Deposit amounts (computed unconditionally for templates) ──────────
    uw_deposit: float = _calc_deposit(
        underweight, known_sectors, sector_weights, total_equity
    )
    div_deposit: float = _calc_deposit(
        dividend_sector, known_sectors, sector_weights, total_equity
    )

    # After-deposit sector percentages (for underweight scenario)
    if uw_deposit > 0:
        _new_total = total_equity + uw_deposit
        new_top_pct_after: float = (
            sector_weights.get(top_sector, 0.0) / _new_total * 100
        )
        new_uw_pct_after: float = (
            (sector_weights.get(underweight, 0.0) + uw_deposit) / _new_total * 100
        )
    else:
        new_top_pct_after = top_sector_pct
        new_uw_pct_after = sector_weights.get(underweight, 0.0) / total_equity * 100

    # ── Single-position helpers ───────────────────────────────────────────
    n_pos: int = len(positions)
    single_ticker: str = positions[0]['ticker'] if n_pos == 1 else ''
    single_sector: str = (positions[0].get('sector') or 'Unknown') if n_pos == 1 else ''

    d: str = dir_label.lower()
    _HIGH_VOL_THRESHOLD = 70

    # ── Action priority ───────────────────────────────────────────────────
    action: str
    if n_pos == 1:
        action = 'single_position'
    elif concentrated_stock is not None:
        action = 'high_single_stock'
    elif top_sector_pct > 55.0:
        action = 'high_sector_concentration'
    elif vol_score >= _HIGH_VOL_THRESHOLD and d in ('depreciating', 'weak'):
        action = 'high_volatility_downtrend'
    elif vol_score >= _HIGH_VOL_THRESHOLD and d in ('strong', 'steady'):
        action = 'high_volatility_uptrend'
    elif sector_count < 3:
        action = 'low_diversification'
    elif d == 'weak':
        action = 'weak_downtrend'
    elif d == 'depreciating':
        action = 'depreciating_trend'
    elif d == 'strong':
        action = 'strong_momentum'
    elif sharpe_val is not None and sharpe_val < 0:
        action = 'negative_sharpe'
    elif beta_val is not None and beta_val > 1.4:
        action = 'high_beta'
    elif not has_dividend_positions and n_pos >= 3:
        action = 'low_yield_opportunity'
    elif d in ('neutral', 'steady') and top_sector_pct < 40.0 and sector_count >= 3:
        action = 'neutral_diversified'
    else:
        action = 'well_positioned'

    color: str = _COLORS[action]

    # ── Template selection ────────────────────────────────────────────────
    idx: int = _pick_template(action, positions)
    s1_tmpl, s2_tmpl = _TEMPLATES[action][idx]

    # ── Context dict ──────────────────────────────────────────────────────
    ctx: dict[str, Any] = {
        # Single-position
        'ticker':                    single_ticker,
        'sector':                    single_sector,
        # Stock concentration
        'concentrated_stock':        concentrated_stock or most_concentrated_ticker,
        'concentrated_stock_pct':    concentrated_stock_pct or most_concentrated_pct,
        # Sector breakdown
        'top_sector':                top_sector,
        'top_sector_pct':            top_sector_pct,
        'remaining_pct':             100.0 - top_sector_pct,
        'equal_weight_pct':          100.0 / max(sector_count, 1),
        'new_top_pct_after':         new_top_pct_after,
        'new_uw_pct_after':          new_uw_pct_after,
        # 10 % move impact for the concentrated stock
        'impact_10pct':              (concentrated_stock_pct or most_concentrated_pct) * 0.10,
        'second_sector':             second_sector,
        'sector_count':              sector_count,
        'sector_plural':             's' if sector_count != 1 else '',
        # Portfolio size
        'position_count':            n_pos,
        # Direction
        'direction_label':           dir_label,
        'slope_annual':              weighted_slope * 252,
        # Volatility
        'vol_score':                 vol_score,
        'vol_label':                 vol_label,
        # Performance extremes
        'most_volatile_ticker':      most_volatile_ticker,
        'most_volatile_vol':         most_volatile_vol,
        'worst_ticker':              worst_ticker,
        'worst_slope_annual':        worst_slope * 252,
        'best_ticker':               best_ticker,
        'best_slope_annual':         best_slope * 252,
        # Advanced metrics
        'sharpe':                    sharpe_val if sharpe_val is not None else 0.0,
        'beta':                      beta_val if beta_val is not None else 1.0,
        'hhi':                       hhi,
        'max_single_stock_pct':      max_single_stock_pct,
        'dividend_yield':            div_yield_val if div_yield_val is not None else 0.0,
        # Underweight sector
        'underweight_sector':        underweight,
        'underweight_tickers':       underweight_tickers_str,
        'underweight_ticker1':       underweight_ticker1,
        'underweight_ticker2':       underweight_ticker2,
        'underweight_ticker3':       underweight_ticker3,
        'underweight_sector_note':   underweight_sector_note,
        'deposit_amount':            uw_deposit,
        'deposit_amount_str':        f'${uw_deposit:,.0f}',
        # Dividend sector
        'dividend_sector':           dividend_sector,
        'div_ticker1':               div_ticker1,
        'div_ticker2':               div_ticker2,
        'dividend_sector_note':      dividend_sector_note,
        'div_deposit_str':           f'${div_deposit:,.0f}',
    }

    try:
        s1 = s1_tmpl.format(**ctx)
        s2 = s2_tmpl.format(**ctx)
    except (KeyError, ValueError) as exc:
        _log.debug('lens template format failed: %s', exc)
        s1 = (
            'This portfolio is being tracked — check back after a full refresh'
            ' for updated analytics.'
        )
        s2 = (
            'Ensure all positions have up-to-date price data for the most'
            ' accurate Lens output.'
        )

    # ── Recommended tickers ───────────────────────────────────────────────
    _diversification_actions = frozenset({
        'single_position', 'high_single_stock', 'high_sector_concentration',
        'low_diversification', 'neutral_diversified',
    })
    if action in _diversification_actions:
        recommended_tickers: list[str] = _sector_ticker_list(underweight, held_tickers)
    elif action == 'low_yield_opportunity':
        recommended_tickers = _sector_ticker_list(dividend_sector, held_tickers)
    else:
        recommended_tickers = []

    if not recommended_tickers:
        recommended_tickers = sorted(slopes, key=slopes.__getitem__, reverse=True)[:3]

    # ── Return deposit amount (Monte Carlo uses this) ─────────────────────
    _rebalancing_actions = frozenset({
        'single_position', 'high_single_stock', 'high_sector_concentration',
        'low_diversification', 'neutral_diversified', 'low_yield_opportunity',
    })
    if action in _rebalancing_actions:
        return_deposit: float = (
            div_deposit if action == 'low_yield_opportunity' else uw_deposit
        )
        return_underweight: str = (
            dividend_sector if action == 'low_yield_opportunity' else underweight
        )
    else:
        return_deposit = 0.0
        return_underweight = ''

    # ── Snapshot ──────────────────────────────────────────────────────────
    _save_snapshot({
        'timestamp':               datetime.now(timezone.utc).isoformat(),
        'portfolio_state':         action,
        'direction_label':         dir_label,
        'direction_slope':         round(weighted_slope, 6),
        'volatility_label':        vol_label,
        'volatility_score':        vol_score,
        'sharpe_ratio':            round(sharpe_val, 4) if sharpe_val is not None else None,
        'beta':                    round(beta_val, 4) if beta_val is not None else None,
        'total_equity':            round(total_equity, 2),
        'position_count':          n_pos,
        'sector_count':            sector_count,
        'top_sector':              top_sector,
        'top_sector_pct':          round(top_sector_pct, 2),
        'hhi':                     round(hhi, 2),
        'max_single_stock_pct':    round(max_single_stock_pct, 2),
        'selected_action':         action,
        'recommended_tickers':     recommended_tickers,
        'deposit_amount':          round(return_deposit, 2) if return_deposit else None,
        'underweight_sector':      return_underweight or None,
        'dividend_yield_portfolio': (
            round(div_yield_val, 4) if div_yield_val is not None else None
        ),
    })

    return (
        s1 + '  ' + s2,
        color,
        recommended_tickers,
        return_deposit,
        return_underweight,
    )
