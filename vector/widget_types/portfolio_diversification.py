from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QWidget, QScrollArea, QFrame
from PyQt6.QtGui import QFont, QColor, QPainter
from PyQt6.QtCore import Qt, QRectF

from vector.widget_base import VectorWidget

_MUTED = '#8d98af'
_ACCENT = ['#3A8DFF', '#8B3FCF', '#E91E8C', '#FF6B2B', '#54BFFF', '#B44AE6',
           '#4ade80', '#f3b84b', '#f87171', '#38bdf8']


def _title_font(size: int = 22) -> QFont:
    f = QFont()
    f.setPointSize(size)
    f.setBold(True)
    return f


class _SectorBar(QWidget):
    """Single horizontal bar row: [dot] sector name [bar] pct%"""

    def __init__(self, sector: str, pct: float, color: str, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        self._pct = pct
        self._color = QColor(color)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        dot = QLabel('●')
        dot.setFixedWidth(14)
        dot.setStyleSheet(f'color: {color}; font-size: 10px; border: none;')
        row.addWidget(dot)

        name = QLabel(sector)
        name.setStyleSheet('font-size: 12px; border: none;')
        name.setMinimumWidth(80)
        row.addWidget(name, stretch=2)

        self._bar_widget = _Bar(pct, color)
        row.addWidget(self._bar_widget, stretch=3)

        pct_lbl = QLabel(f'{pct:.1f}%')
        pct_lbl.setFixedWidth(44)
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pct_lbl.setStyleSheet('font-size: 12px; font-weight: 700; border: none;')
        row.addWidget(pct_lbl)


class _Bar(QWidget):
    def __init__(self, pct: float, color: str, parent=None) -> None:
        super().__init__(parent)
        self._pct = pct
        self._color = QColor(color)
        self.setFixedHeight(8)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        # Track
        painter.setBrush(QColor('#1e2840'))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        # Fill
        fill_w = max(0.0, w * self._pct / 100.0)
        if fill_w > 0:
            painter.setBrush(self._color)
            painter.drawRoundedRect(QRectF(0, 0, fill_w, h), h / 2, h / 2)


class PortfolioDiversificationWidget(VectorWidget):
    NAME = 'Diversification'
    DESCRIPTION = 'Sector allocation breakdown with concentration insight.'
    DEFAULT_ROWSPAN = 3
    DEFAULT_COLSPAN = 4

    def __init__(self, window=None, parent=None) -> None:
        super().__init__(window=window, parent=parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title_lbl = QLabel('Diversification')
        title_lbl.setFont(_title_font(22))
        title_lbl.setStyleSheet('color: #e7ebf3; border: none;')
        header.addWidget(title_lbl)
        header.addStretch(1)
        self._sector_count_lbl = QLabel('')
        self._sector_count_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 11px; border: none;')
        header.addWidget(self._sector_count_lbl)
        layout.addLayout(header)

        # Insight line
        self._insight_lbl = QLabel('')
        self._insight_lbl.setWordWrap(True)
        self._insight_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 11px; border: none;')
        layout.addWidget(self._insight_lbl)

        # Sector bars container
        self._bars_widget = QWidget()
        self._bars_widget.setStyleSheet('background: transparent;')
        self._bars_layout = QVBoxLayout(self._bars_widget)
        self._bars_layout.setContentsMargins(0, 0, 0, 0)
        self._bars_layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidget(self._bars_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('background: transparent; border: none;')
        layout.addWidget(scroll, stretch=1)

    def refresh(self) -> None:
        if not self._window:
            return
        positions = self._window.positions or []

        # Clear bars
        while self._bars_layout.count():
            item = self._bars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not positions:
            self._sector_count_lbl.setText('')
            self._insight_lbl.setText('Add positions to see allocation.')
            self._bars_layout.addStretch(1)
            return

        # Build sector map weighted by equity
        total_equity = sum(p.get('equity', 0) for p in positions)
        sector_map: dict[str, float] = {}
        for p in positions:
            sector = p.get('sector') or 'Unknown'
            sector_map[sector] = sector_map.get(sector, 0.0) + p.get('equity', 0.0)

        allocation = sorted(sector_map.items(), key=lambda x: x[1], reverse=True)
        self._sector_count_lbl.setText(f'{len(allocation)} sector{"s" if len(allocation) != 1 else ""}')

        top_sector, top_equity = allocation[0] if allocation else ('', 0)
        top_pct = (top_equity / total_equity * 100) if total_equity else 0
        if top_pct >= 70:
            self._insight_lbl.setText(f'{top_pct:.0f}% concentrated in {top_sector} — consider diversifying.')
        elif top_pct >= 45:
            self._insight_lbl.setText(f'{top_pct:.0f}% in {top_sector} — moderate concentration.')
        else:
            self._insight_lbl.setText('Allocation is well spread across sectors.')

        for i, (sector, equity) in enumerate(allocation):
            pct = (equity / total_equity * 100) if total_equity else 0
            color = _ACCENT[i % len(_ACCENT)]
            self._bars_layout.addWidget(_SectorBar(sector, pct, color))

        self._bars_layout.addStretch(1)
