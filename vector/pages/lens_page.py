from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .dashboard import _CONTENT_W

if TYPE_CHECKING:
    from vector.app import VectorMainWindow


class _GraphCard(QFrame):
    """
    Card widget containing a title label and a lazy matplotlib projection graph.
    The canvas is created on first call to plot() to avoid importing matplotlib
    at startup.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('cardFrame')
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(16, 16, 16, 12)
        self._outer.setSpacing(10)

        self._title_lbl = QLabel(title)
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        self._title_lbl.setFont(f)
        self._title_lbl.setStyleSheet('font-size: 12pt; font-weight: 700;')
        self._title_lbl.setWordWrap(True)
        self._outer.addWidget(self._title_lbl)

        self._placeholder = QLabel('Loading projection…')
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet('color: #8d98af; font-size: 11pt;')
        self._placeholder.setMinimumHeight(280)
        self._outer.addWidget(self._placeholder, stretch=1)

        self._canvas = None
        self._ax = None
        self._fig = None

    def set_title(self, title: str) -> None:
        self._title_lbl.setText(title)

    def _ensure_canvas(self) -> None:
        if self._canvas is not None:
            return
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        self._fig = Figure(facecolor='#161b26')
        self._fig.subplots_adjust(left=0.04, right=0.86, top=0.95, bottom=0.14)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(280)
        # Pass scroll events up to the parent QScrollArea instead of consuming them
        self._canvas.wheelEvent = lambda event: event.ignore()
        self._placeholder.hide()
        self._outer.addWidget(self._canvas, stretch=1)

    def show_no_data(self, msg: str = 'Insufficient data for projection') -> None:
        self._placeholder.setText(msg)
        self._placeholder.show()
        if self._canvas is not None:
            self._canvas.hide()

    def plot(
        self,
        hist_days: list[int],
        hist_values: list[float],
        future_days: list[int],
        bands: dict,
        median: Any,
        fan_color: str = '#34a7ff',
        ylim: tuple[float, float] | None = None,
    ) -> None:
        """Draw historical curve + Monte Carlo fan on the embedded axes."""
        import numpy as np
        from matplotlib.ticker import FuncFormatter

        self._ensure_canvas()
        if self._canvas is not None:
            self._canvas.show()
        self._placeholder.hide()

        ax = self._ax
        ax.clear()

        # --- Normalisation base: today = 0% ---
        today_value = float(median[0]) if median is not None and len(median) else (
            hist_values[-1] if hist_values else 1.0
        )
        if today_value <= 0:
            today_value = 1.0

        def to_pct(v: float | np.ndarray) -> float | np.ndarray:
            return (np.asarray(v, dtype=float) / today_value - 1.0) * 100.0

        ax.set_facecolor('#121828')
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis='both', colors='#8d98af', labelsize=8)
        ax.grid(True, color='#2a3142', alpha=0.5, linewidth=0.5, zorder=0)

        ax.yaxis.tick_right()
        ax.yaxis.set_label_position('right')

        if hist_days and hist_values:
            ax.plot(
                list(hist_days) + [0],
                list(to_pct(np.array(hist_values))) + [0.0],
                color='#34a7ff', lw=1.5, zorder=3,
            )

        ax.axvline(x=0, color='#8d98af', lw=1.0, ls='--', alpha=0.55, zorder=2)

        if bands and future_days:
            alphas = {(10, 90): 0.12, (25, 75): 0.22, (40, 60): 0.35}
            fd = np.array(future_days)
            for band_key in [(10, 90), (25, 75), (40, 60)]:
                if band_key in bands:
                    lo_arr, hi_arr = bands[band_key]
                    ax.fill_between(
                        fd, to_pct(lo_arr), to_pct(hi_arr),
                        alpha=alphas[band_key], color=fan_color, zorder=1,
                        linewidth=0,
                    )
            if median is not None:
                ax.plot(
                    fd, to_pct(np.asarray(median, dtype=float)),
                    color=fan_color, lw=1.5, ls='--', alpha=0.9, zorder=3,
                )

        def _fmt(v: float, _pos: int) -> str:
            return f'{v:+.1f}%' if v != 0 else '0%'

        ax.yaxis.set_major_formatter(FuncFormatter(_fmt))

        xticks = [0, 21, 42, 63, 84, 105]
        xlabels = ['Today', '1m', '2m', '3m', '4m', '5m']
        ax.set_xticks(xticks)
        ax.set_xticklabels(xlabels, color='#8d98af', fontsize=8)

        if ylim is not None:
            ax.set_ylim(*ylim)

        self._canvas.draw()


class _PieCard(QFrame):
    """Card widget containing a title label and a donut pie chart with legend."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('cardFrame')
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(16, 16, 16, 12)
        self._outer.setSpacing(10)

        self._title_lbl = QLabel(title)
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        self._title_lbl.setFont(f)
        self._title_lbl.setStyleSheet('font-size: 12pt; font-weight: 700;')
        self._title_lbl.setWordWrap(True)
        self._outer.addWidget(self._title_lbl)

        self._placeholder = QLabel('Add positions to see allocation.')
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet('color: #8d98af; font-size: 11pt;')
        self._placeholder.setMinimumHeight(240)
        self._outer.addWidget(self._placeholder, stretch=1)

        self._content = QWidget()
        self._content.setStyleSheet('background: transparent;')
        content_layout = QHBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        from vector.widget_types.portfolio_diversification import _DonutChart
        self._donut = _DonutChart()
        self._donut.setMinimumHeight(220)
        content_layout.addWidget(self._donut, stretch=3)

        self._legend_widget = QWidget()
        self._legend_widget.setStyleSheet('background: transparent;')
        self._legend_layout = QVBoxLayout(self._legend_widget)
        self._legend_layout.setContentsMargins(0, 0, 0, 0)
        self._legend_layout.setSpacing(2)
        content_layout.addWidget(self._legend_widget, stretch=2)

        self._outer.addWidget(self._content, stretch=1)
        self._content.hide()

    def set_title(self, title: str) -> None:
        self._title_lbl.setText(title)

    def show_empty(self, msg: str = 'No data.') -> None:
        self._content.hide()
        self._placeholder.setText(msg)
        self._placeholder.show()

    def refresh(self, sector_map: dict) -> None:
        from vector.widget_types.portfolio_diversification import _LegendRow, _PIE_COLORS

        while self._legend_layout.count():
            item = self._legend_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not sector_map:
            self.show_empty()
            return

        self._placeholder.hide()
        self._content.show()

        total = sum(sector_map.values()) or 1.0
        allocation = sorted(sector_map.items(), key=lambda x: x[1], reverse=True)

        slices: list[tuple[float, str]] = []
        for i, (sector, equity) in enumerate(allocation):
            pct = equity / total * 100
            color = _PIE_COLORS[i % len(_PIE_COLORS)]
            slices.append((pct, color))
            self._legend_layout.addWidget(_LegendRow(sector, pct, color))

        self._legend_layout.addStretch(1)
        self._donut.set_slices(slices)


class VectorLensPage(QWidget):
    """Dedicated page for Vector Lens — projection graphs and pie charts."""

    def __init__(self, window: 'VectorMainWindow') -> None:
        super().__init__()
        self.window = window
        self._build_ui()

    def _build_ui(self) -> None:
        from vector.widget_types.lens import LensDisplay

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setFixedWidth(_CONTENT_W)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 24)
        layout.setSpacing(16)

        self._lens = LensDisplay(window=self.window, show_button=False)
        self._lens.setFixedHeight(200)
        layout.addWidget(self._lens)

        graphs_row = QWidget()
        graphs_layout = QHBoxLayout(graphs_row)
        graphs_layout.setContentsMargins(0, 0, 0, 0)
        graphs_layout.setSpacing(16)
        self._graph_a = _GraphCard('Current Portfolio')
        self._graph_b = _GraphCard('With Lens')
        graphs_layout.addWidget(self._graph_a)
        graphs_layout.addWidget(self._graph_b)
        layout.addWidget(graphs_row)

        pies_row = QWidget()
        pies_layout = QHBoxLayout(pies_row)
        pies_layout.setContentsMargins(0, 0, 0, 0)
        pies_layout.setSpacing(16)
        self._pie_a = _PieCard('Current Allocation')
        self._pie_b = _PieCard('With Lens')
        pies_layout.addWidget(self._pie_a)
        pies_layout.addWidget(self._pie_b)
        layout.addWidget(pies_row)

        layout.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll, stretch=1)

    def refresh(self) -> None:
        self._lens.refresh()
        recommended_tickers = list(getattr(self._lens, '_recommended_tickers', []))
        self._update_graphs(recommended_tickers)
        self._update_pies(recommended_tickers)

    def _update_graphs(self, recommended_tickers: list[str]) -> None:
        from vector.monte_carlo import build_historical_curve, run_projection

        positions = self.window.positions or []
        store = self.window.store
        settings = self.window.settings
        refresh_interval = settings.get('refresh_interval', '5 min')

        if not positions:
            self._graph_a.show_no_data('Add positions to see projections.')
            self._graph_b.show_no_data('Add positions to see projections.')
            return

        total_equity = sum(p.get('equity', 0.0) for p in positions) or 1.0
        tickers = [p['ticker'] for p in positions]
        weights = [p.get('equity', 0.0) / total_equity for p in positions]

        hist_days, hist_values = build_historical_curve(
            positions, store, refresh_interval, num_days=60,
        )

        try:
            result_a = run_projection(tickers, weights, total_equity, store, refresh_interval)
        except Exception:  # noqa: BLE001
            result_a = None

        if recommended_tickers:
            raw_deposit = getattr(self._lens, '_deposit_amount', 0.0)
            deposit = raw_deposit if raw_deposit > 0 else 0.1 * total_equity
            per_ticker = deposit / len(recommended_tickers)
            new_total = total_equity + deposit

            equity_map: dict[str, float] = {p['ticker']: p.get('equity', 0.0) for p in positions}
            for t in recommended_tickers:
                equity_map[t] = equity_map.get(t, 0.0) + per_ticker

            all_tickers = list(equity_map.keys())
            all_weights = [equity_map[t] / new_total for t in all_tickers]

            try:
                result_b = run_projection(all_tickers, all_weights, total_equity, store,
                                          refresh_interval)
            except Exception:  # noqa: BLE001
                result_b = None
        else:
            result_b = None

        display_b = result_b if result_b is not None else result_a

        import numpy as np

        def _pct_extremes(res: tuple | None) -> list[float]:
            if res is None:
                return []
            _, bands, med = res
            base = float(med[0]) if med is not None and len(med) else 1.0
            if base <= 0:
                return []
            lo, hi = bands.get((10, 90), (np.array([]), np.array([])))
            hist_pct = [((v / base) - 1) * 100 for v in (hist_values or [])]
            band_pct = (((np.asarray(lo) / base) - 1) * 100).tolist() + \
                       (((np.asarray(hi) / base) - 1) * 100).tolist()
            return hist_pct + band_pct

        all_pct = _pct_extremes(result_a) + _pct_extremes(display_b)
        if all_pct:
            pad = (max(all_pct) - min(all_pct)) * 0.06
            shared_ylim: tuple[float, float] | None = (min(all_pct) - pad, max(all_pct) + pad)
        else:
            shared_ylim = None

        if result_a is not None:
            future_days, bands_a, median_a = result_a
            self._graph_a.plot(hist_days, hist_values, future_days, bands_a, median_a,
                               fan_color='#34a7ff', ylim=shared_ylim)
        else:
            self._graph_a.show_no_data('Insufficient history for projection.')

        if display_b is not None:
            future_days_b, bands_b, median_b = display_b
            if recommended_tickers and result_b is not None:
                raw_deposit = getattr(self._lens, '_deposit_amount', 0.0)
                deposit = raw_deposit if raw_deposit > 0 else 0.1 * total_equity
                tickers_str = ', '.join(recommended_tickers)
                dep_fmt = f'${deposit:,.0f}'
                b_title = f'With Lens  —  {dep_fmt} into {tickers_str}'
            else:
                b_title = 'With Lens'
            self._graph_b.set_title(b_title)
            self._graph_b.plot(hist_days, hist_values, future_days_b, bands_b, median_b,
                               fan_color='#a256f6', ylim=shared_ylim)
        else:
            self._graph_b.show_no_data('No lens guidance available.')

    def _update_pies(self, recommended_tickers: list[str]) -> None:
        positions = self.window.positions or []

        if not positions:
            self._pie_a.show_empty('Add positions to see allocation.')
            self._pie_b.show_empty('Add positions to see allocation.')
            return

        total_equity = sum(p.get('equity', 0.0) for p in positions) or 1.0

        current_sector_map: dict[str, float] = {}
        for p in positions:
            sector = p.get('sector') or 'Unknown'
            current_sector_map[sector] = current_sector_map.get(sector, 0.0) + p.get('equity', 0.0)

        self._pie_a.refresh(current_sector_map)

        if recommended_tickers:
            deposit = getattr(self._lens, '_deposit_amount', 0.0)
            if deposit <= 0:
                deposit = 0.1 * total_equity
            underweight_sector = getattr(self._lens, '_underweight_sector', '') or 'Unknown'

            post_sector_map = dict(current_sector_map)
            post_sector_map[underweight_sector] = post_sector_map.get(underweight_sector, 0.0) + deposit

            self._pie_b.refresh(post_sector_map)
            dep_fmt = f'${deposit:,.0f}'
            self._pie_b.set_title(f'With Lens  —  {dep_fmt} into {underweight_sector}')
        else:
            self._pie_b.refresh(current_sector_map)
            self._pie_b.set_title('With Lens')
