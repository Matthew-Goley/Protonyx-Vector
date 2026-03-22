from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QWidget
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtCore import Qt, QRectF

from vector.widget_base import VectorWidget


# ---------------------------------------------------------------------------
# Inline sparkline — 4:1 width:height, no external dependency
# ---------------------------------------------------------------------------

class _Sparkline4x1(QWidget):
    """Thin sparkline that enforces a 4:1 draw-area aspect ratio."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._values: list[float] = []
        self._color = QColor('#4ade80')
        self.setMinimumHeight(30)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    def set_values(self, values: list[float], color: str = '#4ade80') -> None:
        self._values = values
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        if len(self._values) < 2:
            painter.setPen(QPen(QColor('#4a5568'), 1))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '—')
            return

        # Enforce 4:1 ratio — height drives width cap
        avail = self.rect().adjusted(2, 2, -2, -2)
        h = float(avail.height())
        max_w = h * 4.0
        w = min(float(avail.width()), max_w)
        x0 = avail.left() + (avail.width() - w) / 2.0
        rect = QRectF(x0, float(avail.top()), w, h)

        low = min(self._values)
        high = max(self._values)
        spread = max(high - low, 1e-9)
        step = rect.width() / max(len(self._values) - 1, 1)

        path = QPainterPath()
        for i, v in enumerate(self._values):
            x = rect.left() + i * step
            y = rect.bottom() - ((v - low) / spread) * rect.height()
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        painter.setPen(QPen(self._color, 2.0,
                            Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)


# ---------------------------------------------------------------------------
# TotalEquityWidget
# ---------------------------------------------------------------------------

_GREEN = '#4ade80'
_RED   = '#f87171'
_MUTED = '#8d98af'


class TotalEquityWidget(VectorWidget):
    NAME = 'Total Equity'
    DESCRIPTION = 'Portfolio value with 5-day performance and sparkline.'
    DEFAULT_ROWSPAN = 2
    DEFAULT_COLSPAN = 4

    def __init__(self, window=None, parent=None) -> None:
        super().__init__(window=window, parent=parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(4)

        # Label row: "Total Equity" title + change badge on the right
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel('Total Equity')
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet('border: none;')
        header_row.addWidget(title_lbl)
        header_row.addStretch(1)

        self._change_lbl = QLabel('')
        self._change_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 13px; border: none;')
        self._change_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self._change_lbl)

        layout.addLayout(header_row)

        # Equity value — large, color coded
        self._value_lbl = QLabel('—')
        value_font = QFont()
        value_font.setPointSize(22)
        value_font.setBold(True)
        self._value_lbl.setFont(value_font)
        self._value_lbl.setStyleSheet('border: none;')
        layout.addWidget(self._value_lbl)

        # Spacer
        layout.addSpacing(6)

        # 5-day sparkline
        self._chart = _Sparkline4x1()
        self._chart.setFixedHeight(52)
        layout.addWidget(self._chart, stretch=1)

    def refresh(self) -> None:
        if not self._window:
            return

        positions = self._window.positions or []
        store = self._window.store
        refresh_interval = self._window.settings.get('refresh_interval', '5 min')
        fmt = self._window.format_currency

        if not positions:
            self._value_lbl.setText(fmt(0))
            self._value_lbl.setStyleSheet('border: none;')
            self._change_lbl.setText('')
            self._chart.set_values([])
            return

        # Build per-hour total equity using 5d/1h data (~32 points)
        daily_totals: list[float] = []
        for pos in positions:
            try:
                closes = store.get_closes(pos['ticker'], '5d', '1h', refresh_interval)
            except Exception:  # noqa: BLE001
                closes = []
            shares = pos.get('shares', 0)
            if not closes:
                continue
            if not daily_totals:
                daily_totals = [shares * c for c in closes]
            else:
                n = min(len(daily_totals), len(closes))
                daily_totals = daily_totals[:n]
                daily_totals = [daily_totals[i] + shares * closes[i] for i in range(n)]

        # Current equity fallback: sum from live positions
        current_equity = sum(p.get('equity', p.get('shares', 0) * p.get('current_price', 0))
                             for p in positions)

        if daily_totals:
            first = daily_totals[0]
            last = daily_totals[-1]
        else:
            first = last = current_equity

        change = last - first
        pct = (change / first * 100) if first else 0.0
        color = _GREEN if change >= 0 else _RED
        sign = '+' if change >= 0 else ''

        # Update labels
        self._value_lbl.setText(fmt(last if daily_totals else current_equity))
        self._value_lbl.setStyleSheet(f'color: {color}; border: none;')
        self._change_lbl.setText(
            f'{sign}{fmt(change)} ({sign}{pct:.2f}%) 5d'
        )
        self._change_lbl.setStyleSheet(f'color: {color}; font-size: 11px; border: none;')
        self._chart.set_values(daily_totals if daily_totals else [current_equity], color)
