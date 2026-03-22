"""
Recommendation engine for Vector.

Generates two plain-English sentences based on live portfolio state:
  Sentence 1 — prediction/outlook  (where is this going?)
  Sentence 2 — action              (what should the owner do right now?)

Logic priority:
  1. Identify the single most pressing concern from the portfolio snapshot
  2. Pick the most relevant template for direction × volatility × risk profile
  3. Fill in ticker/sector/value variables for specificity

Templates are stored as lists so future additions are drop-in changes.
"""

from __future__ import annotations

import random
from typing import Any


# ---------------------------------------------------------------------------
# Template banks — each entry is a (condition_key, template_string) pair.
# Variables enclosed in {braces} are filled at render time.
# ---------------------------------------------------------------------------

_OUTLOOK: dict[str, list[str]] = {

    # direction × volatility
    'strong_low': [
        "{top} is leading a clean rally — the data points to continued appreciation if market conditions hold.",
        "Your portfolio is building real momentum with {top} at the front — current slope projects further upside.",
        "Strong, low-noise upward movement across your holdings suggests the trend has legs.",
    ],
    'strong_high': [
        "Gains are strong but {volatile} is introducing turbulence — momentum is real and vulnerable to sharp pullbacks.",
        "Your portfolio is rising fast, driven largely by {volatile} — a high-reward position that could reverse quickly.",
        "Upside is clear, but volatility from {volatile} means this rally could retrace before it extends.",
    ],
    'steady_low': [
        "{top} is anchoring consistent progress — this is the profile of a portfolio in a healthy accumulation phase.",
        "Steady appreciation with minimal noise suggests your holdings are compounding quietly — a positive sign.",
        "Your portfolio is growing at a sustainable pace, with {top} providing the clearest contribution.",
    ],
    'steady_high': [
        "Growth is present but {volatile} is adding noise — the trend is positive and not yet clean enough to trust fully.",
        "Modest upward slope is competing with elevated swings from {volatile} — the direction is right, stability is not.",
    ],
    'neutral_low': [
        "Your portfolio is in consolidation — {top} is your most stable anchor but no position is creating meaningful movement.",
        "Sideways price action with low volatility suggests the market is coiling — a directional move is likely building.",
        "Flat slope across holdings means no clear edge right now; this is a waiting period, not a warning.",
    ],
    'neutral_high': [
        "Your portfolio is going nowhere fast but swinging hard — {volatile} is generating noise without generating returns.",
        "High volatility with no direction is the worst risk profile — you're taking the risk without the reward.",
        "Choppy, directionless movement from {volatile} is eroding capital without producing gains.",
    ],
    'depreciating_low': [
        "{worst} is leading your portfolio into a measured decline — the slope is negative and unlikely to reverse without a catalyst.",
        "Your holdings are trending downward, slowly but consistently — {worst} is the primary contributor to the slide.",
    ],
    'depreciating_high': [
        "{worst} is driving your portfolio lower with increasing volatility — this combination typically accelerates before it stabilizes.",
        "Declining momentum with elevated swings in {worst} is a warning sign — this move has room to get worse before it gets better.",
    ],
    'weak_low': [
        "Your portfolio is in a sustained downtrend led by {worst} — the data shows no reversal signal at this time.",
        "Significant downward pressure is building across your holdings, with {worst} absorbing the most damage.",
    ],
    'weak_high': [
        "{worst} is accelerating a high-volatility selloff — this is the profile of a portfolio under real stress.",
        "Strong downward momentum and elevated volatility in {worst} is a dangerous combination — losses can compound quickly here.",
        "Your portfolio is falling hard and fast, with {worst} leading the decline — the current trajectory points to further losses.",
    ],
}

_ACTION: dict[str, list[str]] = {

    # primary concern → action
    'concentrate_single': [
        "Trim {top} down from {top_pct:.0f}% of your portfolio — that level of single-stock exposure turns any bad quarter into a portfolio event.",
        "{top} at {top_pct:.0f}% of your holdings means one bad earnings or macro shock hits you disproportionately — rebalance now while the position is strong.",
        "Your biggest risk right now is {top}, not the market — reduce that {top_pct:.0f}% weight before it forces the decision for you.",
    ],
    'concentrate_sector': [
        "You're {top_pct:.0f}% exposed to {sector} — adding a position in {alt_sector} would immediately reduce your sector risk without sacrificing growth.",
        "{sector} dominates your portfolio at {top_pct:.0f}% — one sector-wide shock and all your positions move together; diversify into {alt_sector}.",
        "Consider rotating part of your {sector} exposure into {alt_sector} — concentration at {top_pct:.0f}% leaves no buffer if the sector corrects.",
    ],
    'high_vol_downtrend': [
        "Set a stop-loss below {worst} now — high volatility during a downtrend means drawdowns can accelerate before you react.",
        "Reduce your {worst} position or hedge it — combining falling momentum with high volatility historically precedes the sharpest losses.",
        "Exit or cut {worst} — you are paying volatility premium for a position that is moving against you; that math gets worse before it gets better.",
    ],
    'high_vol_uptrend': [
        "Set a trailing stop on {best} to protect gains — high-volatility rallies retrace faster than they form, and giving back gains here is easy.",
        "Consider locking in partial profits on {best} — you have made real money on a volatile position, and the risk of a reversal is elevated.",
        "Use this strength in {best} to take partial profits — volatility cuts both ways and the gains are real only once realized.",
    ],
    'neutral_diversify': [
        "Use this flat period to add a position in {alt_sector} — building diversification costs less when prices aren't moving.",
        "While your portfolio consolidates, open a position in {alt_sector} — sideways markets are the lowest-cost time to rebalance.",
        "This is the right moment to add {alt_sector} exposure — entering a new sector during flat conditions avoids chasing momentum.",
    ],
    'strong_hold': [
        "Stay the course — the trend in {top} is healthy and there is no technical or fundamental signal to step aside from this move.",
        "Let {top} run — you have momentum, manageable volatility, and no concentration alert; the right action here is patience.",
        "Hold your positions and let the compounding work — your portfolio is trending well with no urgent risks to address.",
    ],
    'depreciating_review': [
        "Review {worst} and set a clear exit level — the trend is down and holding a declining position without a stop is capital destruction.",
        "Consider cutting {worst} or at minimum setting a hard stop — the slope says this position is losing value faster than the market.",
        "{worst} is your most urgent problem — either define your exit price now or accept that you're letting the market decide for you.",
    ],
    'weak_cut': [
        "Cut {worst} now — the data shows strong downward momentum and no near-term reversal signal; holding is a bet against the trend.",
        "Your {worst} position is in a confirmed downtrend with high volatility — the risk-reward of staying in is deeply negative.",
        "Reduce or exit {worst} immediately — strong downward momentum at elevated volatility is the highest-risk profile in your portfolio.",
    ],
    'single_position': [
        "You are entirely concentrated in {top} — adding even one uncorrelated position would dramatically reduce your all-or-nothing risk.",
        "A single-position portfolio means your entire financial picture moves with {top} — diversify as soon as possible.",
    ],
    'few_positions': [
        "With only {n_pos} positions, one bad holding will dominate your results — adding {alt_sector} exposure would meaningfully spread that risk.",
        "Your portfolio is small enough that one underperformer defines your returns — consider adding a position in {alt_sector} to create a buffer.",
    ],
}

# ---------------------------------------------------------------------------
# Sector suggestion map
# ---------------------------------------------------------------------------

_SECTOR_ALTERNATIVES: dict[str, str] = {
    'Technology':            'Healthcare',
    'Healthcare':            'Technology',
    'Financial Services':    'Consumer Defensive',
    'Financials':            'Consumer Defensive',
    'Consumer Cyclical':     'Consumer Defensive',
    'Consumer Defensive':    'Technology',
    'Energy':                'Technology',
    'Industrials':           'Technology',
    'Communication Services':'Healthcare',
    'Utilities':             'Technology',
    'Real Estate':           'Technology',
    'Basic Materials':       'Technology',
    'Unknown':               'Technology',
}

_ALL_SECTORS = list(_SECTOR_ALTERNATIVES.keys())


def _alt_sector(held_sectors: set[str]) -> str:
    """Return the first well-known sector the user doesn't hold."""
    preferred = ['Technology', 'Healthcare', 'Consumer Defensive',
                 'Financial Services', 'Industrials', 'Energy']
    for s in preferred:
        if s not in held_sectors:
            return s
    return 'a different sector'


def _pick(templates: list[str], seed_key: str) -> str:
    """Deterministically pick a template variant using a hash seed."""
    idx = hash(seed_key) % len(templates)
    return templates[idx]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_recommendation(
    positions: list[dict[str, Any]],
    store,
    settings: dict[str, Any],
) -> tuple[str, str, str]:
    """
    Return (sentence1, sentence2, color) based on current portfolio state.
    color is a hex string matching the overall sentiment.
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
            'Add positions to get personalised recommendations.',
            'Go to Settings to add your first holding.',
            '#8d98af',
        )

    refresh_interval = settings.get('refresh_interval', '5 min')
    thresholds = settings.get('direction_thresholds', {
        'strong': 0.18, 'steady': 0.05,
        'neutral_low': -0.05, 'neutral_high': 0.05,
        'depreciating': -0.18,
    })
    vol_settings = settings.get('volatility', {})
    lookback = vol_settings.get('lookback', '6 months')
    period = VOLATILITY_LOOKBACK_PERIODS.get(lookback, '6mo')
    low_cut = int(vol_settings.get('low_cutoff', 30))
    high_cut = int(vol_settings.get('high_cutoff', 60))

    total_equity = sum(p.get('equity', 0) for p in positions)

    # Per-ticker metrics
    slopes:     dict[str, float] = {}
    vols:       dict[str, float] = {}
    equities:   dict[str, float] = {}

    for pos in positions:
        t = pos['ticker']
        eq = pos.get('equity', 0.0)
        equities[t] = eq
        try:
            closes_6m = store.get_history(t, '6mo', refresh_interval)
            slopes[t] = linear_regression_slope_percent(closes_6m)
        except Exception:  # noqa: BLE001
            slopes[t] = 0.0
        try:
            closes_p = store.get_history(t, period, refresh_interval)
            vols[t] = annualized_volatility(closes_p)
        except Exception:  # noqa: BLE001
            vols[t] = 0.0

    weighted_slope = sum(slopes[t] * equities[t] / total_equity for t in slopes) if total_equity else 0.0
    weighted_vol   = sum(vols[t]   * equities[t] / total_equity for t in vols)   if total_equity else 0.0

    dir_label, dir_color, _ = classify_direction(weighted_slope, thresholds)
    vol_score = score_volatility(weighted_vol)
    vol_label, _ = classify_volatility(vol_score, low_cut, high_cut)

    top_ticker   = max(equities, key=equities.get)
    best_ticker  = max(slopes,   key=slopes.get)
    worst_ticker = min(slopes,   key=slopes.get)
    vol_ticker   = max(vols,     key=vols.get)
    top_equity_pct = equities[top_ticker] / total_equity * 100 if total_equity else 0

    sector_map: dict[str, float] = {}
    for p in positions:
        s = p.get('sector') or 'Unknown'
        sector_map[s] = sector_map.get(s, 0.0) + p.get('equity', 0.0)
    top_sector = max(sector_map, key=sector_map.get) if sector_map else 'Unknown'
    top_sector_pct = sector_map.get(top_sector, 0) / total_equity * 100 if total_equity else 0
    held_sectors = set(sector_map.keys())
    alt_sector_name = _alt_sector(held_sectors)

    n_pos = len(positions)
    seed = top_ticker + dir_label + vol_label  # consistent across refreshes

    # ── Outlook sentence ──────────────────────────────────────────────────
    is_high_vol = vol_label == 'High Risk'
    is_low_vol  = vol_label == 'Low Volatility'
    dir_key = dir_label.lower().replace(' ', '_').replace('volatility', '').strip('_')
    # map to template keys
    dir_map = {
        'strong': 'strong', 'steady': 'steady', 'neutral': 'neutral',
        'depreciating': 'depreciating', 'weak': 'weak',
    }
    d = dir_map.get(dir_key, 'neutral')
    v = 'high' if is_high_vol else 'low'
    outlook_key = f'{d}_{v}'
    outlook_templates = _OUTLOOK.get(outlook_key, _OUTLOOK['neutral_low'])
    outlook = _pick(outlook_templates, seed + 'o').format(
        top=top_ticker, best=best_ticker, worst=worst_ticker,
        volatile=vol_ticker, sector=top_sector, alt_sector=alt_sector_name,
        top_pct=top_equity_pct, n_pos=n_pos,
    )

    # ── Action sentence — prioritise by urgency ───────────────────────────
    if n_pos == 1:
        action_key = 'single_position'
    elif top_equity_pct >= 55:
        action_key = 'concentrate_single'
    elif top_sector_pct >= 75:
        action_key = 'concentrate_sector'
    elif d in ('weak',) :
        action_key = 'weak_cut'
    elif d == 'depreciating' and is_high_vol:
        action_key = 'high_vol_downtrend'
    elif d == 'depreciating':
        action_key = 'depreciating_review'
    elif d in ('strong', 'steady') and is_high_vol:
        action_key = 'high_vol_uptrend'
    elif d == 'neutral' and n_pos < 4:
        action_key = 'few_positions' if n_pos <= 3 else 'neutral_diversify'
    elif d in ('strong', 'steady') and is_low_vol:
        action_key = 'strong_hold'
    else:
        action_key = 'neutral_diversify'

    action_templates = _ACTION[action_key]
    action = _pick(action_templates, seed + 'a').format(
        top=top_ticker, best=best_ticker, worst=worst_ticker,
        volatile=vol_ticker, sector=top_sector, alt_sector=alt_sector_name,
        top_pct=top_equity_pct, n_pos=n_pos,
    )

    return outlook, action, dir_color
