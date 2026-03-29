"""
Monte Carlo projection engine for Vector.

Uses Geometric Brownian Motion (GBM) to project portfolio equity forward.
Portfolio-level volatility is computed from the full covariance matrix so
that diversification correctly narrows the projected fan (ρ < 1 between
uncorrelated sectors reduces portfolio sigma vs. the weighted-average).
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from vector.store import DataStore


def build_historical_curve(
    positions: list[dict],
    store: 'DataStore',
    refresh_interval: str,
    num_days: int = 60,
) -> tuple[list[int], list[float]]:
    """
    Reconstruct a portfolio equity curve using share counts × historical prices.

    Returns (day_indices, values) where day_indices are negative integers
    ending at -1, e.g. [-59, -58, ..., -1].  Returns ([], []) when no
    usable history is available.
    """
    hist_map: dict[str, list[float]] = {}
    for pos in positions:
        t = pos['ticker']
        try:
            hist = store.get_history(t, '6mo', refresh_interval)
            if hist and len(hist) >= 5:
                hist_map[t] = hist
        except Exception:  # noqa: BLE001
            pass

    if not hist_map:
        return [], []

    min_len = min(len(v) for v in hist_map.values())
    clip = min(min_len, num_days)

    portfolio_values: list[float] = []
    for j in range(clip):
        day_value = 0.0
        for pos in positions:
            t = pos['ticker']
            shares = pos.get('shares', 0.0)
            if t in hist_map:
                price = hist_map[t][-(clip - j)]
            else:
                price = pos.get('price', pos.get('equity', 0.0) / max(shares, 1e-9))
            day_value += shares * price
        portfolio_values.append(max(day_value, 0.0))

    day_indices = list(range(-clip, 0))
    return day_indices, portfolio_values


def run_projection(
    tickers: list[str],
    weights: list[float],
    current_value: float,
    store: 'DataStore',
    refresh_interval: str = '5 min',
    num_paths: int = 200,
    horizon_days: int = 120,
) -> tuple[list[int], dict[tuple[int, int], tuple[np.ndarray, np.ndarray]], np.ndarray] | None:
    """
    Run a GBM Monte Carlo projection for a portfolio.

    Portfolio mu and sigma are derived from the actual covariance matrix of
    daily log-returns so that diversification into low-correlation assets
    correctly reduces projected volatility (narrower fan).

    Args:
        tickers:          Ticker symbols.
        weights:          Portfolio weight per ticker (must sum to ~1.0).
        current_value:    Starting portfolio value (today).
        store:            DataStore for fetching yfinance-backed price history.
        refresh_interval: Cache TTL setting string (e.g. '5 min').
        num_paths:        Number of GBM simulation paths.
        horizon_days:     Trading days to project forward.

    Returns:
        (future_day_indices, percentile_bands, median_path)
            future_day_indices = [0, 1, ..., horizon_days]
            percentile_bands   = {(10,90): (lo, hi), (25,75): ..., (40,60): ...}
        Returns None if current_value <= 0.
    """
    if current_value <= 0:
        return None

    # --- Collect per-ticker daily log-return series ---
    return_series: list[np.ndarray] = []
    valid_weights: list[float] = []

    for ticker, weight in zip(tickers, weights):
        if weight <= 0:
            continue

        hist: list[float] = []
        try:
            hist = store.get_history(ticker, '1y', refresh_interval)
        except Exception:  # noqa: BLE001
            pass

        if hist and len(hist) >= 20:
            prices = np.array(hist, dtype=float)
            log_rets = np.diff(np.log(np.maximum(prices, 1e-10)))
        else:
            # Fallback: synthetic returns with broad-market assumptions.
            # Each missing ticker gets an independent series (ρ≈0 with others),
            # so it still contributes a diversification benefit.
            rng_fb = np.random.default_rng(seed=abs(hash(ticker)) % (2 ** 31))
            log_rets = rng_fb.normal(0.10 / 252.0, 0.20 / math.sqrt(252.0), 252)

        return_series.append(log_rets)
        valid_weights.append(weight)

    if not return_series:
        return None

    # --- Align all series to the same length (trim to shortest) ---
    min_len = min(len(r) for r in return_series)
    aligned = np.array([r[-min_len:] for r in return_series])  # (n, min_len)

    w = np.array(valid_weights, dtype=float)
    w /= w.sum()

    # --- Portfolio mu: weighted average of annualised daily means ---
    daily_means = aligned.mean(axis=1)
    port_mu = float(w @ daily_means) * 252.0

    # --- Portfolio sigma: from covariance matrix (wᵀ Σ w), annualised ---
    # This correctly reflects diversification: uncorrelated assets (off-diagonal
    # covariances ≈ 0) produce a lower portfolio variance than the weighted sum
    # of individual variances would suggest.
    if len(return_series) == 1:
        cov_daily = np.array([[float(aligned[0].var(ddof=1))]])
    else:
        cov_daily = np.cov(aligned, ddof=1)  # (n, n) daily covariance matrix

    port_variance_annual = float(w @ cov_daily @ w) * 252.0
    port_sigma = max(math.sqrt(max(port_variance_annual, 0.0)), 0.01)

    # --- GBM simulation ---
    dt = 1.0 / 252.0
    rng = np.random.default_rng(seed=42)  # fixed seed → stable fan shape
    drift = (port_mu - 0.5 * port_sigma ** 2) * dt
    diffusion = port_sigma * math.sqrt(dt)

    Z = rng.standard_normal((num_paths, horizon_days))
    log_steps = drift + diffusion * Z                      # (num_paths, horizon_days)
    cumulative = np.cumsum(log_steps, axis=1)              # (num_paths, horizon_days)

    paths = np.empty((num_paths, horizon_days + 1))
    paths[:, 0] = current_value
    paths[:, 1:] = current_value * np.exp(cumulative)

    pct_bands: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
    for lo, hi in [(10, 90), (25, 75), (40, 60)]:
        pct_bands[(lo, hi)] = (
            np.percentile(paths, lo, axis=0),
            np.percentile(paths, hi, axis=0),
        )

    median_path = np.percentile(paths, 50, axis=0)
    return list(range(horizon_days + 1)), pct_bands, median_path
