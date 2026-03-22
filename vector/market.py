from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import yfinance as yf

from .constants import REFRESH_INTERVAL_MINUTES, VOLATILITY_LOOKBACK_PERIODS
from .storage import StorageManager


class MarketDataService:
    def __init__(self, storage: StorageManager) -> None:
        self.storage = storage

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _is_cache_fresh(self, timestamp: str | None, refresh_interval: str) -> bool:
        minutes = REFRESH_INTERVAL_MINUTES.get(refresh_interval)
        if refresh_interval == 'Manual only':
            return bool(timestamp)
        if not timestamp or minutes is None:
            return False
        cached_at = datetime.fromisoformat(timestamp)
        return (self._now() - cached_at) < timedelta(minutes=minutes)

    def validate_ticker(self, ticker: str) -> dict[str, Any]:
        clean = ticker.strip().upper()
        if not clean:
            raise ValueError('Ticker symbol is required.')
        instrument = yf.Ticker(clean)
        info = instrument.fast_info or {}
        meta = instrument.info or {}
        current_price = info.get('lastPrice') or meta.get('currentPrice') or meta.get('regularMarketPrice')
        sector = meta.get('sector') or meta.get('industryDisp') or 'Unknown'
        if current_price in (None, 0):
            history = instrument.history(period='5d', interval='1d', auto_adjust=False)
            if history.empty:
                raise ValueError(f'Unable to validate ticker {clean} with Yahoo Finance.')
            current_price = float(history['Close'].dropna().iloc[-1])
        return {
            'ticker': clean,
            'price': float(current_price),
            'sector': sector,
            'name': meta.get('shortName') or clean,
        }

    def get_snapshot(self, ticker: str, refresh_interval: str) -> dict[str, Any]:
        cache = self.storage.load_price_cache()
        item = cache.get(ticker, {})
        if item and self._is_cache_fresh(item.get('snapshot_updated_at'), refresh_interval):
            return item['snapshot']
        snapshot = self.validate_ticker(ticker)
        cache.setdefault(ticker, {})['snapshot'] = snapshot
        cache[ticker]['snapshot_updated_at'] = self._now().isoformat()
        self.storage.save_price_cache(cache)
        return snapshot

    def get_history(self, ticker: str, period: str, refresh_interval: str) -> list[float]:
        cache = self.storage.load_price_cache()
        item = cache.get(ticker, {})
        histories = item.get('history', {})
        history_meta = item.get('history_updated_at', {})
        if period in histories and self._is_cache_fresh(history_meta.get(period), refresh_interval):
            return histories[period]
        frame = yf.Ticker(ticker).history(period=period, interval='1d', auto_adjust=False)
        closes = [float(value) for value in frame['Close'].dropna().tolist()]
        cache.setdefault(ticker, {}).setdefault('history', {})[period] = closes
        cache[ticker].setdefault('history_updated_at', {})[period] = self._now().isoformat()
        self.storage.save_price_cache(cache)
        return closes

    def build_histories(self, tickers: list[str], refresh_interval: str, lookback: str) -> dict[str, dict[str, list[float]]]:
        period_key = VOLATILITY_LOOKBACK_PERIODS.get(lookback, '6mo')
        histories: dict[str, dict[str, list[float]]] = {}
        for ticker in tickers:
            histories[ticker] = {
                '6mo': self.get_history(ticker, '6mo', refresh_interval),
                '1mo': self.get_history(ticker, '1mo', refresh_interval),
                period_key: self.get_history(ticker, period_key, refresh_interval),
            }
        return histories
