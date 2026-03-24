from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont, QColor, QPainter
from PyQt6.QtCore import Qt, QRectF, QTimer

from vector.widget_base import VectorWidget
from vector.recommendations import generate_recommendation

_MUTED = '#8d98af'
_BG    = '#121828'


def _font(size: int, bold: bool = True) -> QFont:
    f = QFont()
    f.setPointSize(size)
    f.setBold(bold)
    return f


class _AccentFrame(QFrame):
    """Card with a colored left accent bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._accent = QColor('#3A8DFF')

    def set_accent(self, color: str) -> None:
        self._accent = QColor(color)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Background
        painter.setBrush(QColor(_BG))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(self.rect()), 12, 12)
        # Left accent bar
        accent = QColor(self._accent)
        accent.setAlpha(200)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(0, 16, 4, self.height() - 32), 2, 2)
        # Border
        border = QColor(self._accent)
        border.setAlpha(60)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        from PyQt6.QtGui import QPen
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 12, 12)


class RecommendationWidget(VectorWidget):
    NAME = 'Recommendation'
    DESCRIPTION = "Vector's Core Functionality"
    DEFAULT_ROWSPAN = 2
    DEFAULT_COLSPAN = 10

    def __init__(self, window=None, parent=None) -> None:
        super().__init__(window=window, parent=parent)
        self._tw_timer = QTimer(self)
        self._tw_timer.setInterval(14)
        self._tw_timer.timeout.connect(self._tw_step)
        self._tw_queue: list[tuple[QLabel, str, str]] = []  # (label, full_text, style)
        self._tw_label: QLabel | None = None
        self._tw_full = ''
        self._tw_style = ''
        self._tw_pos = 0
        # Override default border style — _AccentFrame handles painting
        self.setStyleSheet('background: transparent; border: none;')

        self._card = _AccentFrame(self)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(22, 18, 22, 18)
        card_layout.setSpacing(14)

        # Title row
        header = QHBoxLayout()
        title = QLabel('Recommendation')
        title.setFont(_font(11, bold=False))
        title.setStyleSheet(f'color: {_MUTED}; border: none;')
        header.addWidget(title)
        header.addStretch(1)
        self._status_lbl = QLabel('')
        self._status_lbl.setFont(_font(10, bold=False))
        self._status_lbl.setStyleSheet(f'color: {_MUTED}; border: none;')
        header.addWidget(self._status_lbl)
        card_layout.addLayout(header)

        # Sentence 1 — outlook
        self._s1 = QLabel('—')
        self._s1.setFont(_font(18))
        self._s1.setWordWrap(True)
        self._s1.setStyleSheet('border: none;')
        card_layout.addWidget(self._s1)

        # Divider label
        divider = QLabel('ACTION')
        divider.setFont(_font(9, bold=False))
        divider.setStyleSheet(f'color: {_MUTED}; letter-spacing: 2px; border: none;')
        card_layout.addWidget(divider)

        # Sentence 2 — action
        self._s2 = QLabel('—')
        self._s2.setFont(_font(18))
        self._s2.setWordWrap(True)
        self._s2.setStyleSheet('border: none;')
        card_layout.addWidget(self._s2)

        card_layout.addStretch(1)

        # Make card fill the widget
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._card)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._card.setGeometry(self.rect())
        super().resizeEvent(event)

    def _apply_style(self, edit: bool) -> None:
        # Override base — let _AccentFrame handle painting
        border = '#3A8DFF' if edit else 'transparent'
        self.setStyleSheet(f'background: transparent; border: 2px solid {border}; border-radius: 12px;')

    def _tw_step(self) -> None:
        self._tw_pos += 1
        self._tw_label.setText(self._tw_full[:self._tw_pos])
        if self._tw_pos >= len(self._tw_full):
            self._tw_timer.stop()
            self._tw_label = None
            # Start next item in queue
            if self._tw_queue:
                label, text, style = self._tw_queue.pop(0)
                self._start_typewrite(label, text, style)

    def _start_typewrite(self, label: QLabel, text: str, style: str) -> None:
        self._tw_timer.stop()
        self._tw_label = label
        self._tw_full = text
        self._tw_style = style
        self._tw_pos = 0
        label.setStyleSheet(style)
        label.setText('')
        self._tw_timer.start()

    def _typewrite(self, s1: str, s1_style: str, s2: str, s2_style: str) -> None:
        self._tw_timer.stop()
        self._tw_queue.clear()
        self._s1.setText('')
        self._s2.setText('')
        self._tw_queue.append((self._s2, s2, s2_style))
        self._start_typewrite(self._s1, s1, s1_style)

    def refresh(self) -> None:
        if not self._window:
            return

        positions = self._window.positions or []
        store = self._window.store
        settings = self._window.settings

        try:
            outlook, action, color = generate_recommendation(positions, store, settings)
        except Exception:  # noqa: BLE001
            outlook = 'Unable to generate recommendation.'
            action  = 'Check your positions and try refreshing.'
            color   = _MUTED

        self._status_lbl.setText('updated')
        self._card.set_accent(color)
        self._typewrite(
            outlook, 'border: none; color: #e7ebf3;',
            action, f'color: {color}; font-weight: 700; border: none;',
        )
