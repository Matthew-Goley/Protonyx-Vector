"""
Registry of all VectorWidget subclasses available in the dashboard.

To add a new widget type:
1. Add a .py file in vector/widget_types/
2. Define a class that subclasses VectorWidget
3. Import it here and add it to _WIDGETS
"""

from vector.widget_base import VectorWidget
from vector.widget_types.dividend_calendar import DividendCalendarWidget
from vector.widget_types.portfolio_beta import PortfolioBetaWidget
from vector.widget_types.portfolio_diversification import PortfolioDiversificationWidget
from vector.widget_types.portfolio_vector import PortfolioVectorWidget
from vector.widget_types.portfolio_volatility import PortfolioVolatilityWidget
from vector.widget_types.positions_list import PositionsListWidget
from vector.widget_types.recommendation import RecommendationWidget
from vector.widget_types.sharpe_ratio import SharpeRatioWidget
from vector.widget_types.total_equity import TotalEquityWidget

_WIDGETS: list[type[VectorWidget]] = [
    RecommendationWidget,
    DividendCalendarWidget,
    PortfolioBetaWidget,
    PortfolioDiversificationWidget,
    PortfolioVectorWidget,
    PortfolioVolatilityWidget,
    PositionsListWidget,
    SharpeRatioWidget,
    TotalEquityWidget,
]


def discover_widgets() -> list[type[VectorWidget]]:
    """Return all registered VectorWidget subclasses."""
    return _WIDGETS


def get_widget_class(class_name: str) -> type[VectorWidget] | None:
    """Look up a widget class by its Python class name."""
    return next((c for c in _WIDGETS if c.__name__ == class_name), None)
