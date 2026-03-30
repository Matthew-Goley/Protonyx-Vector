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
) -> tuple[str, str, list[str], float, str, str]:
    """
    Analyse the portfolio and return a 6-tuple:

    - ``text``                — two plain-English observational sentences
    - ``color``               — hex color reflecting portfolio state
    - ``recommended_tickers`` — tickers relevant to the selected action
    - ``deposit_amount``      — dollar amount for Monte Carlo Graph B (0.0 if N/A)
    - ``underweight_sector``  — sector used for deposit math ('' if N/A)
    - ``action_type``         — one of "buy" / "sell" / "rebalance" / "hold"
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
    from .constants import (
        INDEX_ETFS,
        LOW_BETA_BY_SECTOR,
        SECTOR_SUGGESTIONS,
        VOLATILITY_LOOKBACK_PERIODS,
    )

    # ── Empty portfolio ───────────────────────────────────────────────────
    if not positions:
        return (
            'Add your first position to see Lens analytics tailored to your'
            ' actual holdings. Go to Settings and add a stock or ETF ticker'
            ' to get started.',
            '#8d98af', [], 0.0, '', 'hold',
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
    _ls: dict[str, Any] = settings.get('lens_signals', {})
    _stock_conc_pct: float = float(_ls.get('stock_concentration_pct', 35))
    _sector_conc_pct: float = float(_ls.get('sector_concentration_pct', 50))
    _steep_dt_pct: float = float(_ls.get('steep_downtrend_pct', -20))
    _high_beta: float = float(_ls.get('high_beta_threshold', 1.3))
    _stock_vol_pct: float = float(_ls.get('stock_vol_threshold_pct', 45)) / 100.0

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

    # Skip index ETFs for single-stock concentration check
    concentrated_stock: str | None = None
    concentrated_stock_pct: float = 0.0
    for t, pct in stock_pcts.items():
        if pct > _stock_conc_pct and t not in INDEX_ETFS:
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

    # ── New signal pre-computation ─────────────────────────────────────────

    # Signal 2 — Steep downtrend: any non-index position with annualised slope ≤ threshold
    _steep_candidates = sorted(
        (
            (t, slopes[t] * 252)
            for t in slopes
            if slopes[t] * 252 <= _steep_dt_pct and t not in INDEX_ETFS
        ),
        key=lambda x: x[1],  # most negative first
    )
    steep_ticker: str = _steep_candidates[0][0] if _steep_candidates else ''
    steep_slope_annual: float = _steep_candidates[0][1] if _steep_candidates else 0.0
    steep_ticker_pct: float = stock_pcts.get(steep_ticker, 0.0)

    # Signal 3 — Excessive single-stock volatility: annualised vol > threshold AND weight > 15%
    _ev_candidates = sorted(
        (
            (t, vols[t] * 100, stock_pcts.get(t, 0.0))
            for t in vols
            if vols[t] > _stock_vol_pct and stock_pcts.get(t, 0.0) > 15.0
            and t not in INDEX_ETFS
        ),
        key=lambda x: x[1],
        reverse=True,  # most volatile first
    )
    ev_ticker: str = _ev_candidates[0][0] if _ev_candidates else ''
    ev_vol: float = _ev_candidates[0][1] if _ev_candidates else 0.0
    ev_pct: float = _ev_candidates[0][2] if _ev_candidates else 0.0

    # Signal 4 — Winner concentration drift: weight > 30% AND slope > +15% annualised
    _drift_candidates = sorted(
        (
            (t, stock_pcts[t])
            for t in stock_pcts
            if stock_pcts[t] > 30.0
            and slopes.get(t, 0.0) * 252 > 15.0
            and t not in INDEX_ETFS
        ),
        key=lambda x: x[1],
        reverse=True,
    )
    drift_ticker: str = _drift_candidates[0][0] if _drift_candidates else ''
    drift_ticker_pct: float = _drift_candidates[0][1] if _drift_candidates else 0.0

    # Signal 5 — Index fund awareness: any INDEX_ETF position with weight > 30%
    _index_candidates = sorted(
        (
            (p['ticker'], equities.get(p['ticker'], 0.0) / total_equity * 100)
            for p in positions
            if p['ticker'] in INDEX_ETFS
            and equities.get(p['ticker'], 0.0) / total_equity * 100 > 30.0
        ),
        key=lambda x: x[1],
        reverse=True,
    )
    index_ticker: str = _index_candidates[0][0] if _index_candidates else ''
    index_pct: float = _index_candidates[0][1] if _index_candidates else 0.0

    # Signal 6 — High portfolio beta: pre-computed, beta_val > 1.3
    _low_beta_suggestions: list[str] = []
    _low_beta_sector_name: str = ''
    for _s in known_sectors:
        _lb_cands = [t for t in LOW_BETA_BY_SECTOR.get(_s, []) if t not in held_tickers]
        if _lb_cands:
            _low_beta_suggestions.extend(_lb_cands[:2])
            _low_beta_sector_name = _low_beta_sector_name or _s
        if len(_low_beta_suggestions) >= 2:
            break
    low_beta_ticker1: str = _low_beta_suggestions[0] if len(_low_beta_suggestions) > 0 else 'lower-beta names'
    low_beta_ticker2: str = _low_beta_suggestions[1] if len(_low_beta_suggestions) > 1 else low_beta_ticker1
    low_beta_sector: str = _low_beta_sector_name or (next(iter(known_sectors), '') if known_sectors else '')
    beta_impact: float = (beta_val or 1.0) * 5.0

    # Signal 11 — Dead weight: weight < 2% AND flat/negative slope (≤ +2% annualised)
    _dw_candidates = sorted(
        (
            (t, stock_pcts[t], slopes.get(t, 0.0) * 252)
            for t in stock_pcts
            if stock_pcts[t] < 2.0
            and slopes.get(t, 0.0) * 252 <= 2.0
            and t not in INDEX_ETFS
        ),
        key=lambda x: (x[1], x[2]),  # smallest weight first, then lowest slope
    )
    dw_ticker: str = _dw_candidates[0][0] if _dw_candidates else ''
    dw_pct: float = _dw_candidates[0][1] if _dw_candidates else 0.0
    dw_slope_annual: float = _dw_candidates[0][2] if _dw_candidates else 0.0

    # Signal 12 — Underrepresented sector: 3+ sectors, one sector has only 1 stock and < 10% weight
    _sector_tickers_map: dict[str, list[str]] = {}
    for _p in positions:
        _s2 = _p.get('sector') or 'Unknown'
        _sector_tickers_map.setdefault(_s2, []).append(_p['ticker'])

    _thin_candidates = [
        (_s3, _sector_tickers_map[_s3][0], sector_weights.get(_s3, 0.0) / total_equity * 100)
        for _s3 in _sector_tickers_map
        if len(_sector_tickers_map[_s3]) == 1
        and sector_weights.get(_s3, 0.0) / total_equity * 100 < 10.0
        and _s3 not in ('Unknown', '')
        and _sector_tickers_map[_s3][0] not in INDEX_ETFS
    ]
    _thin_candidates.sort(key=lambda x: x[2])  # smallest sector first
    _thin_info = _thin_candidates[0] if _thin_candidates and sector_count >= 3 else None
    thin_sector: str = _thin_info[0] if _thin_info else ''
    thin_sector_ticker: str = _thin_info[1] if _thin_info else ''
    thin_sector_pct: float = _thin_info[2] if _thin_info else 0.0
    _ts_suggs = [t for t in SECTOR_SUGGESTIONS.get(thin_sector, []) if t not in held_tickers][:2]
    sector_suggestion1: str = _ts_suggs[0] if len(_ts_suggs) > 0 else thin_sector
    sector_suggestion2: str = _ts_suggs[1] if len(_ts_suggs) > 1 else sector_suggestion1

    # Signal 13 — Unrealized loss flag: 6-month price decline > 20%
    _loss_candidates = [
        (t, abs((h[-1] - h[0]) / h[0] * 100))
        for t, h in histories.items()
        if len(h) >= 2 and h[0] > 0 and (h[-1] - h[0]) / h[0] < -0.20
        and t not in INDEX_ETFS
    ]
    _loss_candidates.sort(key=lambda x: x[1], reverse=True)  # largest loss first
    loss_ticker: str = _loss_candidates[0][0] if _loss_candidates else ''
    loss_pct: float = _loss_candidates[0][1] if _loss_candidates else 0.0

    # ── Action priority ───────────────────────────────────────────────────
    action: str
    # 1. Single position
    if n_pos == 1:
        action = 'single_position'
    # 2. Steep downtrend — per-stock
    elif steep_ticker:
        action = 'steep_downtrend'
    # 3. Excessive single-stock volatility
    elif ev_ticker:
        action = 'excessive_stock_vol'
    # 4. Winner concentration drift
    elif drift_ticker:
        action = 'winner_drift'
    # 5. Index fund awareness (preempts sector/stock concentration signals)
    elif index_ticker:
        action = 'index_fund_awareness'
    # 6. High portfolio beta
    elif beta_val is not None and beta_val > _high_beta:
        action = 'high_portfolio_beta'
    # 7. Sector over-concentration
    elif top_sector_pct > _sector_conc_pct:
        action = 'high_sector_concentration'
    # 8. Single-stock concentration (> 35%, non-index)
    elif concentrated_stock is not None:
        action = 'high_single_stock'
    # 9. Portfolio-wide downtrend
    elif vol_score >= _HIGH_VOL_THRESHOLD and d in ('depreciating', 'weak'):
        action = 'high_volatility_downtrend'
    elif d == 'weak':
        action = 'weak_downtrend'
    elif d == 'depreciating':
        action = 'depreciating_trend'
    # 10. High-vol uptrend
    elif vol_score >= _HIGH_VOL_THRESHOLD and d in ('strong', 'steady'):
        action = 'high_volatility_uptrend'
    elif d == 'strong':
        action = 'strong_momentum'
    elif sharpe_val is not None and sharpe_val < 0:
        action = 'negative_sharpe'
    elif sector_count < 3:
        action = 'low_diversification'
    # 11. Dead weight positions
    elif dw_ticker:
        action = 'dead_weight'
    # 12. Underrepresented sector
    elif _thin_info is not None:
        action = 'underrepresented_sector'
    # 13. Unrealized loss flag
    elif loss_ticker:
        action = 'unrealized_loss'
    elif not has_dividend_positions and n_pos >= 3:
        action = 'low_yield_opportunity'
    # 14. Neutral/diversified
    elif d in ('neutral', 'steady') and top_sector_pct < 40.0 and sector_count >= 3:
        action = 'neutral_diversified'
    # 15. Hold fallback
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
        # Signal 2 — steep downtrend
        'declining_ticker':          steep_ticker or worst_ticker,
        'declining_slope_annual':    steep_slope_annual or worst_slope * 252,
        'declining_ticker_pct':      steep_ticker_pct or stock_pcts.get(worst_ticker, 0.0),
        # Signal 3 — excessive single-stock volatility
        'volatile_ticker':           ev_ticker or most_volatile_ticker,
        'volatile_ticker_vol':       ev_vol or most_volatile_vol,
        'volatile_ticker_pct':       ev_pct or stock_pcts.get(most_volatile_ticker, 0.0),
        # Signal 4 — winner drift
        'drift_ticker':              drift_ticker or most_concentrated_ticker,
        'drift_ticker_pct':          drift_ticker_pct or most_concentrated_pct,
        # Signal 5 — index fund awareness
        'index_ticker':              index_ticker or most_concentrated_ticker,
        'index_pct':                 index_pct or most_concentrated_pct,
        # Signal 6 — high portfolio beta
        'low_beta_ticker1':          low_beta_ticker1,
        'low_beta_ticker2':          low_beta_ticker2,
        'low_beta_sector':           low_beta_sector,
        'beta_impact':               beta_impact,
        # Signal 11 — dead weight
        'deadweight_ticker':         dw_ticker or worst_ticker,
        'deadweight_pct':            dw_pct or stock_pcts.get(worst_ticker, 0.0),
        'deadweight_slope_annual':   dw_slope_annual or worst_slope * 252,
        # Signal 12 — underrepresented sector
        'thin_sector':               thin_sector or underweight,
        'thin_sector_ticker':        thin_sector_ticker or underweight_ticker1,
        'thin_sector_pct':           thin_sector_pct,
        'sector_suggestion1':        sector_suggestion1 or underweight_ticker1,
        'sector_suggestion2':        sector_suggestion2 or underweight_ticker2,
        # Signal 13 — unrealized loss
        'loss_ticker':               loss_ticker or worst_ticker,
        'loss_pct':                  loss_pct or abs(worst_slope * 252 * 0.5),
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

    # ── Action type map ───────────────────────────────────────────────────
    _ACTION_TYPES: dict[str, str] = {
        'single_position':           'buy',
        'steep_downtrend':           'sell',
        'excessive_stock_vol':       'sell',
        'winner_drift':              'rebalance',
        'index_fund_awareness':      'hold',
        'high_portfolio_beta':       'buy',
        'high_sector_concentration': 'buy',
        'high_single_stock':         'buy',
        'high_volatility_downtrend': 'sell',
        'weak_downtrend':            'sell',
        'depreciating_trend':        'sell',
        'high_volatility_uptrend':   'hold',
        'strong_momentum':           'hold',
        'negative_sharpe':           'sell',
        'high_beta':                 'buy',
        'low_diversification':       'buy',
        'dead_weight':               'sell',
        'underrepresented_sector':   'buy',
        'unrealized_loss':           'hold',
        'low_yield_opportunity':     'buy',
        'neutral_diversified':       'buy',
        'well_positioned':           'hold',
    }
    action_type: str = _ACTION_TYPES.get(action, 'hold')

    # ── Recommended tickers ───────────────────────────────────────────────
    recommended_tickers: list[str]
    if action in ('single_position', 'high_sector_concentration',
                  'low_diversification', 'neutral_diversified',
                  'high_volatility_downtrend', 'high_volatility_uptrend',
                  'high_beta'):
        recommended_tickers = _sector_ticker_list(underweight, held_tickers)
    elif action == 'high_single_stock':
        recommended_tickers = _sector_ticker_list(underweight, held_tickers)
    elif action == 'low_yield_opportunity':
        recommended_tickers = _sector_ticker_list(dividend_sector, held_tickers)
    elif action == 'high_portfolio_beta':
        recommended_tickers = [t for t in _low_beta_suggestions if t][:3]
    elif action == 'underrepresented_sector':
        recommended_tickers = [t for t in [sector_suggestion1, sector_suggestion2] if t and t != thin_sector]
    else:
        # All other signals (including sell/hold) point the deposit at the underweight sector
        recommended_tickers = _sector_ticker_list(underweight, held_tickers)

    if not recommended_tickers:
        recommended_tickers = sorted(slopes, key=slopes.__getitem__, reverse=True)[:3]

    # ── Return deposit amount — always populated so Monte Carlo Graph B ───
    # and the pie chart have something to display for every signal.
    if action == 'low_yield_opportunity':
        return_deposit: float = div_deposit
        return_underweight: str = dividend_sector
    else:
        return_deposit = uw_deposit
        return_underweight = underweight

    # ── Snapshot ──────────────────────────────────────────────────────────
    _save_snapshot({
        'timestamp':               datetime.now(timezone.utc).isoformat(),
        'portfolio_state':         action,
        'action_type':             action_type,
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
        action_type,
    )
