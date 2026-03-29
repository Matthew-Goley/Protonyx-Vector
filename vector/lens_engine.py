"""
Lens engine for Vector.

Generates exactly two plain-English sentences covering:
  A. Risk right now     — concentration, volatility, diversification
  B. Position awareness — what's moving, what context matters
  C. Next dollar        — where should the next deposit go?

Sentences are picked deterministically from a large template bank
based on portfolio state, so output is stable across refreshes but
changes whenever holdings or analytics actually change.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .lens_templates import _TEMPLATES, _COLORS  # noqa: F401 (re-exported for backwards compat)

# ---------------------------------------------------------------------------
# Template bank — moved to lens_templates.py
# The _TEMPLATES and _COLORS dicts are imported above.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PREFERRED_SECTORS = [
    'Technology', 'Healthcare', 'Consumer Defensive', 'Financial Services',
    'Financials', 'Industrials', 'Energy', 'Consumer Cyclical',
    'Communication Services', 'Utilities', 'Real Estate', 'Basic Materials',
]

# Well-known tickers per sector for concrete suggestions
_SECTOR_TICKERS: dict[str, list[str]] = {
    'Technology':              ['AAPL', 'MSFT', 'NVDA', 'GOOG', 'META'],
    'Healthcare':              ['UNH', 'JNJ', 'PFE', 'ABBV', 'LLY'],
    'Consumer Defensive':      ['PG', 'KO', 'PEP', 'WMT', 'COST'],
    'Financial Services':      ['JPM', 'V', 'BRK-B', 'MA', 'BAC'],
    'Financials':              ['JPM', 'V', 'BRK-B', 'MA', 'BAC'],
    'Industrials':             ['CAT', 'HON', 'UNP', 'GE', 'RTX'],
    'Energy':                  ['XOM', 'CVX', 'COP', 'SLB', 'EOG'],
    'Consumer Cyclical':       ['AMZN', 'TSLA', 'HD', 'NKE', 'MCD'],
    'Communication Services':  ['GOOG', 'META', 'DIS', 'NFLX', 'T'],
    'Utilities':               ['NEE', 'DUK', 'SO', 'D', 'AEP'],
    'Real Estate':             ['AMT', 'PLD', 'CCI', 'O', 'SPG'],
    'Basic Materials':         ['LIN', 'APD', 'SHW', 'ECL', 'NEM'],
}


def _sector_ticker_hint(sector: str, held_tickers: set[str], n: int = 3) -> str:
    """Return '(TICK1, TICK2, TICK3)' for a sector, excluding tickers the user already holds."""
    candidates = _SECTOR_TICKERS.get(sector, [])
    picks = [t for t in candidates if t not in held_tickers][:n]
    if not picks:
        picks = candidates[:n]
    if not picks:
        return ''
    return '(' + ', '.join(picks) + ')'


def _sector_ticker_list(sector: str, held_tickers: set[str], n: int = 3) -> list[str]:
    """Return a list of ticker suggestions for a sector, excluding already-held tickers."""
    candidates = _SECTOR_TICKERS.get(sector, [])
    picks = [t for t in candidates if t not in held_tickers][:n]
    if not picks:
        picks = candidates[:n]
    return picks


def _underweight_sector(held_sectors: set[str], sector_weights: dict[str, float]) -> str:
    """
    Return the best sector to add next:
    - First priority: well-known sectors the user doesn't hold at all
    - Second priority: the lowest-weighted sector the user does hold
    Falls back to a generic phrase if everything is covered.
    """
    for s in _PREFERRED_SECTORS:
        if s not in held_sectors:
            return s
    # All preferred sectors are held — return lowest weighted one
    if sector_weights:
        return min(sector_weights, key=sector_weights.get)
    return 'a different sector'


def _pick_template(state: str, positions: list) -> int:
    """Deterministic template selection — stable across refreshes for the same state."""
    key = state + "|" + ",".join(sorted(p["ticker"] for p in positions))
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return h % len(_TEMPLATES[state])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_lens(
    positions: list[dict[str, Any]],
    store,
    settings: dict[str, Any],
) -> tuple[str, str, list[str], float]:
    """
    Returns (text, color, recommended_tickers, deposit_amount) where:
      text                 — two sentences covering risk and next-deposit guidance
      color                — hex color reflecting portfolio state
      recommended_tickers  — list of tickers suggested for the next deposit
      deposit_amount       — dollar amount needed to bring the recommended sector
                             to equal weight with all other sectors in the portfolio
    """
    from vector.analytics import (
        linear_regression_slope_percent,
        annualized_volatility,
        classify_direction,
        classify_volatility,
        score_volatility,
    )
    from vector.constants import VOLATILITY_LOOKBACK_PERIODS

    if not positions:
        return (
            "Add your first position to get personalised guidance tailored to your actual holdings. "
            "Go to Settings and add a stock or ETF ticker to get started.",
            "#8d98af",
            [],
            0.0,
            '',
        )

    refresh_interval = settings.get('refresh_interval', '5 min')
    thresholds = settings.get('direction_thresholds', {
        'strong': 0.08, 'steady': 0.02,
        'neutral_low': -0.02, 'neutral_high': 0.02,
        'depreciating': -0.08,
    })
    vol_settings = settings.get('volatility', {})
    lookback = vol_settings.get('lookback', '6 months')
    period = VOLATILITY_LOOKBACK_PERIODS.get(lookback, '6mo')
    low_cut = int(vol_settings.get('low_cutoff', 30))
    high_cut = int(vol_settings.get('high_cutoff', 60))

    total_equity = sum(p.get('equity', 0) for p in positions) or 1.0

    # ── Per-ticker metrics ────────────────────────────────────────────────
    slopes:   dict[str, float] = {}
    vols:     dict[str, float] = {}
    equities: dict[str, float] = {}

    for pos in positions:
        t = pos['ticker']
        eq = pos.get('equity', 0.0)
        equities[t] = eq
        try:
            slopes[t] = linear_regression_slope_percent(
                store.get_history(t, '6mo', refresh_interval))
        except Exception:  # noqa: BLE001
            slopes[t] = 0.0
        try:
            vols[t] = annualized_volatility(
                store.get_history(t, period, refresh_interval))
        except Exception:  # noqa: BLE001
            vols[t] = 0.0

    weighted_slope = sum(slopes[t] * equities[t] / total_equity for t in slopes)
    weighted_vol   = sum(vols[t]   * equities[t] / total_equity for t in vols)

    dir_label, _dir_color, _ = classify_direction(weighted_slope, thresholds)
    vol_score = score_volatility(weighted_vol)
    vol_label, _ = classify_volatility(vol_score, low_cut, high_cut)

    # ── Derived values ────────────────────────────────────────────────────
    n_pos         = len(positions)
    biggest_gainer_t = max(slopes, key=slopes.get)
    biggest_loser_t  = min(slopes, key=slopes.get)

    # Sector map
    sector_weights: dict[str, float] = {}
    for p in positions:
        s = p.get('sector') or 'Unknown'
        sector_weights[s] = sector_weights.get(s, 0.0) + p.get('equity', 0.0)

    held_sectors = set(sector_weights.keys())
    top_sector = max(sector_weights, key=sector_weights.get) if sector_weights else 'Unknown'
    top_sector_pct = sector_weights.get(top_sector, 0.0) / total_equity * 100
    second_sector = (
        sorted(sector_weights, key=sector_weights.get, reverse=True)[1]
        if len(sector_weights) >= 2 else top_sector
    )

    # Concentration flags
    concentrated_stock: str | None = None
    concentrated_stock_pct = 0.0
    for t, eq in equities.items():
        pct = eq / total_equity * 100
        if pct > 35:
            concentrated_stock = t
            concentrated_stock_pct = pct
            break

    concentrated_sector: str | None = None
    concentrated_sector_pct = 0.0
    if top_sector_pct > 50:
        concentrated_sector = top_sector
        concentrated_sector_pct = top_sector_pct

    underweight = _underweight_sector(held_sectors, sector_weights)
    held_tickers = {p['ticker'] for p in positions}
    underweight_tickers = _sector_ticker_hint(underweight, held_tickers)

    is_high_vol = vol_label in ('High Risk', 'High Volatility', 'High')
    d = dir_label.lower()

    # ── State classification (first match wins) ───────────────────────────
    if n_pos == 1:
        state = "SINGLE_POSITION"
    elif concentrated_stock is not None:
        state = "CONCENTRATED_STOCK"
    elif concentrated_sector is not None:
        state = "CONCENTRATED_SECTOR"
    elif d in ('weak', 'depreciating') and is_high_vol:
        state = "DOWNTREND_HIGH_VOL"
    elif d in ('weak', 'depreciating'):
        state = "DOWNTREND_LOW_VOL"
    elif d in ('strong', 'steady') and is_high_vol:
        state = "UPTREND_HIGH_VOL"
    elif d in ('strong', 'steady'):
        state = "UPTREND_LOW_VOL"
    elif is_high_vol:
        state = "NEUTRAL_HIGH_VOL"
    else:
        state = "NEUTRAL_LOW_VOL"

    color = _COLORS[state]

    # ── Template selection ────────────────────────────────────────────────
    idx = _pick_template(state, positions)
    s1_tmpl, s2_tmpl = _TEMPLATES[state][idx]

    # Safe fallbacks for edge cases
    if underweight == top_sector:
        underweight = second_sector
        underweight_tickers = _sector_ticker_hint(underweight, held_tickers)

    ctx = dict(
        single_ticker          = positions[0]['ticker'] if n_pos == 1 else '',
        concentrated_stock     = concentrated_stock or '',
        concentrated_stock_pct = concentrated_stock_pct,
        concentrated_sector    = concentrated_sector or top_sector,
        concentrated_sector_pct= concentrated_sector_pct or top_sector_pct,
        underweight_sector     = underweight,
        underweight_sector_tickers = underweight_tickers,
        biggest_gainer         = biggest_gainer_t,
        biggest_loser          = biggest_loser_t,
        biggest_gainer_pct     = slopes.get(biggest_gainer_t, 0.0),
        biggest_loser_pct      = slopes.get(biggest_loser_t, 0.0),
        direction_label        = dir_label,
        direction_slope        = weighted_slope,
        volatility_score       = vol_score,
        volatility_label       = vol_label,
        top_sector             = top_sector,
        top_sector_pct         = top_sector_pct,
        second_sector          = second_sector,
        num_positions          = n_pos,
    )

    try:
        s1 = s1_tmpl.format(**ctx)
        s2 = s2_tmpl.format(**ctx)
    except (KeyError, ValueError):
        s1 = "Your portfolio is being tracked — check back after a full refresh for personalised guidance."
        s2 = "Make sure your positions have up-to-date price data for the best insights."

    # Tickers to suggest for the next deposit (used by Monte Carlo Graph B)
    recommended_tickers = _sector_ticker_list(underweight, held_tickers)
    if not recommended_tickers:
        recommended_tickers = sorted(slopes, key=slopes.get, reverse=True)[:3]

    # ── Deposit amount needed to bring the underweight sector to equal weight ──
    # Formula: solve (current_sector_eq + D) / (total_equity + D) = 1/n
    # → D = (total_equity - n * current_sector_eq) / (n - 1)
    known_sectors = {s for s in held_sectors if s != 'Unknown'}
    n_target = len(known_sectors) + (1 if underweight not in known_sectors else 0)
    n_target = max(n_target, 2)
    current_sector_eq = sector_weights.get(underweight, 0.0)
    raw_deposit = (total_equity - n_target * current_sector_eq) / (n_target - 1)
    deposit_amount = max(raw_deposit, 0.0)

    return s1 + "  " + s2, color, recommended_tickers, deposit_amount, underweight
