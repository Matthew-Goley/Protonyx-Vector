from pathlib import Path

APP_NAME = 'Vector'
COMPANY_NAME = 'Protonyx'
APP_VERSION = '0.1.0'
DATA_DIR = Path.home() / APP_NAME / 'data'
POSITIONS_FILE = DATA_DIR / 'positions.json'
SETTINGS_FILE = DATA_DIR / 'settings.json'
APP_STATE_FILE = DATA_DIR / 'app_state.json'
PRICE_CACHE_FILE = DATA_DIR / 'price_cache.json'  # legacy - superseded by market_data.json
MARKET_DATA_FILE = DATA_DIR / 'market_data.json'
LAYOUT_FILE = DATA_DIR / 'dashboard_layout.json'
LOGO_PATH = Path(__file__).resolve().parent.parent / 'assets' / 'vector_full.png'
TASKBAR_LOGO_PATH = Path(__file__).resolve().parent.parent / 'assets' / 'vector_taskbar.png'

DEFAULT_SETTINGS = {
    'theme': 'Dark',
    'currency': 'USD',
    'date_format': 'MM/DD/YYYY',
    'refresh_interval': '5 min',
    'direction_thresholds': {
        'strong': 0.18,
        'steady': 0.05,
        'neutral_low': -0.05,
        'neutral_high': 0.05,
        'depreciating': -0.18,
    },
    'volatility': {
        'lookback': '6 months',
        'low_cutoff': 30,
        'high_cutoff': 60,
    },
}

DEFAULT_APP_STATE = {
    'onboarding_complete': False,
    'first_launch_date': None,
}

DEFAULT_POSITIONS = []
DEFAULT_PRICE_CACHE = {}
TTL_META_MINUTES         = 1_440   # 24 h — company info rarely changes
TTL_HISTORY_DAILY_MINUTES = 60      # 60 min for 1mo and longer daily bars
TTL_DIVIDENDS_MINUTES    = 1_440   # 24 h
TTL_EARNINGS_MINUTES     = 1_440   # 24 h

REFRESH_INTERVAL_MINUTES = {
    '1 min': 1,
    '5 min': 5,
    '15 min': 15,
    'Manual only': None,
}
VOLATILITY_LOOKBACK_PERIODS = {
    '3 months': '3mo',
    '6 months': '6mo',
    '1 year': '1y',
}
