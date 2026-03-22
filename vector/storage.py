from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import (
    APP_STATE_FILE,
    DATA_DIR,
    DEFAULT_APP_STATE,
    DEFAULT_POSITIONS,
    DEFAULT_PRICE_CACHE,
    DEFAULT_SETTINGS,
    POSITIONS_FILE,
    PRICE_CACHE_FILE,
    SETTINGS_FILE,
)


class StorageManager:
    def __init__(self) -> None:
        self.ensure_data_dir()

    def ensure_data_dir(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path: Path, default: Any) -> Any:
        self.ensure_data_dir()
        if not path.exists():
            self._write_json(path, default)
            return deepcopy(default)
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            self._write_json(path, default)
            return deepcopy(default)

    def _write_json(self, path: Path, payload: Any) -> None:
        self.ensure_data_dir()
        path.write_text(json.dumps(payload, indent=2), encoding='utf-8')

    def load_positions(self) -> list[dict[str, Any]]:
        return self._read_json(POSITIONS_FILE, DEFAULT_POSITIONS)

    def save_positions(self, positions: list[dict[str, Any]]) -> None:
        self._write_json(POSITIONS_FILE, positions)

    def load_settings(self) -> dict[str, Any]:
        settings = self._read_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        merged = deepcopy(DEFAULT_SETTINGS)
        merged.update(settings)
        merged['direction_thresholds'].update(settings.get('direction_thresholds', {}))
        merged['volatility'].update(settings.get('volatility', {}))
        return merged

    def save_settings(self, settings: dict[str, Any]) -> None:
        self._write_json(SETTINGS_FILE, settings)

    def load_app_state(self) -> dict[str, Any]:
        state = self._read_json(APP_STATE_FILE, DEFAULT_APP_STATE)
        merged = deepcopy(DEFAULT_APP_STATE)
        merged.update(state)
        if not merged.get('first_launch_date'):
            merged['first_launch_date'] = datetime.now(timezone.utc).date().isoformat()
            self.save_app_state(merged)
        return merged

    def save_app_state(self, state: dict[str, Any]) -> None:
        self._write_json(APP_STATE_FILE, state)

    def load_price_cache(self) -> dict[str, Any]:
        return self._read_json(PRICE_CACHE_FILE, DEFAULT_PRICE_CACHE)

    def save_price_cache(self, cache: dict[str, Any]) -> None:
        self._write_json(PRICE_CACHE_FILE, cache)

    def clear_price_cache(self) -> None:
        self.save_price_cache({})

    def reset_all_data(self) -> None:
        for file_path, default in (
            (POSITIONS_FILE, DEFAULT_POSITIONS),
            (SETTINGS_FILE, DEFAULT_SETTINGS),
            (APP_STATE_FILE, DEFAULT_APP_STATE),
            (PRICE_CACHE_FILE, DEFAULT_PRICE_CACHE),
        ):
            self._write_json(file_path, default)
