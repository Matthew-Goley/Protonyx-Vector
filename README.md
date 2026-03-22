# Vector by Protonyx

Vector is a PyQt6 desktop portfolio analytics app that uses Yahoo Finance via `yfinance` and persists all user data locally in `~/Vector/data/`.

## Features

- First-launch onboarding with ticker validation.
- Desktop dashboard with portfolio direction, diversification, volatility, and position sparklines.
- Local JSON persistence for positions, settings, app state, and cached market data.
- Settings for refresh intervals, thresholds, volatility bands, theme, currency, and onboarding reset.
- Guest profile page with total value and position table.

## Run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

## Data Storage

Vector stores data in the following files:

- `~/Vector/data/positions.json`
- `~/Vector/data/settings.json`
- `~/Vector/data/app_state.json`
- `~/Vector/data/price_cache.json`

## Logo Asset

- Place your production logo at `assets/vector_logo.png` if you want to replace the built-in fallback.
- If the file is missing, Vector renders a generated placeholder mark automatically so the app still launches cleanly.
