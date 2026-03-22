"""
Portfolio Vector widget — large directional arrow showing the weighted slope of the portfolio.

The arrow runs left-to-right and tilts upward (positive slope) or downward (negative slope).
Slope is the equity-weighted average of each position's 6-month linear regression slope.
Color maps to direction label (Strong / Steady / Neutral / Depreciating / Weak).
Stats are intentionally larger and bolder than other widgets.
"""

import math

from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PyQt6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF,
)
from PyQt6.QtCore import Qt, QPointF, QRectF

from vector.widget_base import VectorWidget
from vector.analytics import linear_regression_slope_percent, classify_direction
from vector.constants import VOLATILITY_LOOKBACK_PERIODS

_MUTED = '#8d98af'


def _title_font(size: int, bold: bool = True) -> QFont:
    f = QFont()
    f.setPointSize(size)
    f.setBold(bold)
    return f


class _VectorArrow(QWidget):
    """
    Horizontal arrow spanning the full width, tilted by angle degrees.
    Positive angle = tilts upward; negative = downward.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._angle = 0.0
        self._color = QColor('#c7cedb')
        self.setMinimumHeight(60)

    def set_state(self, angle: float, color: str) -> None:
        self._angle = max(-55.0, min(55.0, angle))
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        pad_x = 20.0
        mid_y = h / 2.0

        angle_rad = math.radians(self._angle)
        # Total vertical travel from start to end
        dy = math.sin(angle_rad) * (h * 0.44)

        # Arrow start at left-center, end at right offset by full dy
        x0 = pad_x
        y0 = mid_y
        x_end = w - pad_x - 34.0   # leave room for arrowhead
        y_end = mid_y - dy          # Qt y: up = negative

        # Bezier control point: same y as start, 65% along x
        # This makes the curve start nearly horizontal and steepen toward the end —
        # matching the "0,0 → 1,1 → 2,3" acceleration shape.
        x_ctrl = x0 + (x_end - x0) * 0.65
        y_ctrl = y0

        path = QPainterPath()
        path.moveTo(x0, y0)
        path.quadTo(x_ctrl, y_ctrl, x_end, y_end)

        # --- glow ---
        glow_color = QColor(self._color)
        glow_color.setAlpha(40)
        painter.strokePath(path, QPen(glow_color, 20, Qt.PenStyle.SolidLine,
                                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        # --- gradient shaft ---
        grad = QLinearGradient(x0, y0, x_end, y_end)
        fade = QColor(self._color)
        fade.setAlpha(100)
        grad.setColorAt(0.0, fade)
        grad.setColorAt(1.0, self._color)
        painter.strokePath(path, QPen(grad, 7, Qt.PenStyle.SolidLine,
                                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        # --- arrowhead aligned to end tangent ---
        # Tangent at end of quadratic bezier = direction from control to end
        tdx = x_end - x_ctrl
        tdy = y_end - y_ctrl
        tlen = math.hypot(tdx, tdy) or 1.0
        ux, uy = tdx / tlen, tdy / tlen
        px, py = -uy, ux

        head_len, head_half = 26.0, 12.0
        tip = QPointF(x_end + ux * 28.0, y_end + uy * 28.0)
        base_cx = x_end - ux * head_len
        base_cy = y_end - uy * head_len
        poly = QPolygonF([
            tip,
            QPointF(base_cx + px * head_half, base_cy + py * head_half),
            QPointF(base_cx - px * head_half, base_cy - py * head_half),
        ])
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(poly)


class PortfolioVectorWidget(VectorWidget):
    NAME = 'Portfolio Vector'
    DESCRIPTION = 'Directional arrow showing the equity-weighted slope of your portfolio.'
    DEFAULT_ROWSPAN = 3
    DEFAULT_COLSPAN = 4

    def __init__(self, window=None, parent=None) -> None:
        super().__init__(window=window, parent=parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 16)
        outer.setSpacing(0)

        # ── Title ────────────────────────────────────────────────────────
        title_lbl = QLabel('Portfolio Vector')
        title_lbl.setFont(_title_font(12, bold=False))
        title_lbl.setStyleSheet(f'color: {_MUTED}; border: none;')
        outer.addWidget(title_lbl)

        outer.addSpacing(2)

        # ── Direction label (hero stat) ──────────────────────────────────
        self._dir_lbl = QLabel('—')
        self._dir_lbl.setFont(_title_font(580))
        self._dir_lbl.setStyleSheet('border: none;')
        outer.addWidget(self._dir_lbl)

        # ── Slope value ──────────────────────────────────────────────────
        self._slope_lbl = QLabel('')
        self._slope_lbl.setFont(_title_font(380))
        self._slope_lbl.setStyleSheet(f'color: {_MUTED}; border: none;')
        outer.addWidget(self._slope_lbl)

        outer.addSpacing(4)

        # ── Arrow visualization ──────────────────────────────────────────
        self._arrow = _VectorArrow()
        outer.addWidget(self._arrow, stretch=1)

        # ── Bottom row: sub-label ────────────────────────────────────────
        self._sub_lbl = QLabel('6-month linear regression · equity-weighted')
        self._sub_lbl.setFont(_title_font(9, bold=False))
        self._sub_lbl.setStyleSheet(f'color: {_MUTED}; border: none;')
        outer.addWidget(self._sub_lbl)

    def refresh(self) -> None:
        if not self._window:
            return

        positions = self._window.positions or []
        store = self._window.store
        refresh_interval = self._window.settings.get('refresh_interval', '5 min')
        thresholds = self._window.settings.get('direction_thresholds', {
            'strong': 0.18, 'steady': 0.05,
            'neutral_low': -0.05, 'neutral_high': 0.05,
            'depreciating': -0.18,
        })

        if not positions:
            self._dir_lbl.setText('No Data')
            self._dir_lbl.setStyleSheet(f'color: {_MUTED}; border: none;')
            self._slope_lbl.setText('')
            self._arrow.set_state(0.0, _MUTED)
            return

        total_equity = sum(p.get('equity', 0) for p in positions)
        weighted_slope = 0.0

        for pos in positions:
            equity = pos.get('equity', 0.0)
            weight = equity / total_equity if total_equity else 0.0
            try:
                closes = store.get_history(pos['ticker'], '6mo', refresh_interval)
            except Exception:  # noqa: BLE001
                closes = []
            slope = linear_regression_slope_percent(closes)
            weighted_slope += slope * weight

        direction_label, color, arrow_angle = classify_direction(weighted_slope, thresholds)
        sign = '+' if weighted_slope >= 0 else ''

        self._dir_lbl.setText(direction_label)
        self._dir_lbl.setStyleSheet(f'color: {color}; border: none;')
        self._slope_lbl.setText(f'{sign}{weighted_slope:.3f}%')
        self._slope_lbl.setStyleSheet(f'color: {color}; border: none;')
        self._arrow.set_state(arrow_angle, color)
