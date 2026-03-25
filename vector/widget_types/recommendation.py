import re

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont, QColor, QFontMetrics, QLinearGradient, QPainter, QPen
from PyQt6.QtCore import Qt, QRect, QRectF, QTimer

from vector.widget_base import VectorWidget
from vector.recommendations import generate_recommendation

_MUTED      = '#8d98af'
_BG         = '#121828'
_GRAD_START = '#3A8DFF'
_GRAD_MID   = '#7B6EF0'
_GRAD_END   = '#B44AE6'

# Sector names → mid gradient
_SECTORS = {
    'Technology', 'Healthcare', 'Financial Services', 'Financials',
    'Consumer Cyclical', 'Consumer Defensive', 'Energy', 'Industrials',
    'Communication Services', 'Utilities', 'Real Estate', 'Basic Materials', 'ETF',
}

# Financial/portfolio terms → mid gradient
_FINANCIAL_TERMS = {
    'earnings', 'volatility', 'momentum', 'compounding', 'downtrend', 'uptrend',
    'rebalance', 'rebalancing', 'diversify', 'diversification', 'concentration',
    'drawdown', 'correction', 'rally', 'selloff', 'pullback', 'rotation',
    'allocation', 'exposure', 'risk', 'gains', 'losses', 'returns',
    'appreciation', 'depreciation', 'correlation', 'trajectory', 'performance',
    'trend', 'momentum', 'thesis', 'catalyst',
}

# Multi-word action phrases → blue gradient (processed before tokenizing)
_ACTION_PHRASES = [
    'next deposit', 'next buy', 'new money', 'new cash',
    'future deposits', 'next paycheck', 'regular deposits',
    'consistent deposits', 'next move',
]


def _wrap(text: str, color: str) -> str:
    return f'<span style="color:{color};">{text}</span>'


def _apply_to_text(s: str, fn) -> str:
    """Apply fn only to text nodes — skip existing HTML tags."""
    parts = re.split(r'(<[^>]*>)', s)
    return ''.join(fn(p) if not p.startswith('<') else p for p in parts)


def _highlight_html(text: str) -> str:
    """
    Return HTML where important parts are gradient-colored:
      - ticker symbols (ALL-CAPS 2-5 letters)  → blue  #3A8DFF
      - known sector names                      → mid   #7B6EF0
      - financial / portfolio terms             → mid   #7B6EF0
      - action phrases ("next deposit" etc.)    → blue  #3A8DFF
      - numbers / percentages / $ amounts       → purple #B44AE6
      - everything else                         → white #e7ebf3
    """
    s = (text
         .replace('&', '&amp;')
         .replace('<', '&lt;')
         .replace('>', '&gt;'))

    # 1. Multi-word action phrases → blue (before word-level processing)
    for phrase in sorted(_ACTION_PHRASES, key=len, reverse=True):
        s = _apply_to_text(s, lambda chunk, p=phrase: re.sub(
            rf'\b({re.escape(p)})\b',
            lambda m: _wrap(m.group(), _GRAD_START),
            chunk, flags=re.IGNORECASE,
        ))

    # 2. Numbers, percentages, dollar amounts → purple
    s = _apply_to_text(s, lambda chunk: re.sub(
        r'([+\-]?\$?[\d,]+\.?\d*\s*%|[+\-]?\$[\d,]+\.?\d*|\b\d+\.?\d*\b)',
        lambda m: _wrap(m.group(), _GRAD_END) if re.search(r'\d', m.group()) else m.group(),
        chunk,
    ))

    # 3. Sector names → mid (longest first to avoid partial matches)
    for sector in sorted(_SECTORS, key=len, reverse=True):
        s = _apply_to_text(s, lambda chunk, sec=sector: re.sub(
            rf'\b({re.escape(sec)})\b',
            lambda m: _wrap(m.group(), _GRAD_MID),
            chunk,
        ))

    # 4. Financial terms → mid
    if _FINANCIAL_TERMS:
        pattern = '|'.join(re.escape(t) for t in sorted(_FINANCIAL_TERMS, key=len, reverse=True))
        s = _apply_to_text(s, lambda chunk: re.sub(
            rf'\b({pattern})\b',
            lambda m: _wrap(m.group(), _GRAD_MID),
            chunk, flags=re.IGNORECASE,
        ))

    # 5. ALL-CAPS tickers (2–5 letters) → blue (last, so they don't interfere)
    s = _apply_to_text(s, lambda chunk: re.sub(
        r'\b([A-Z]{2,5})\b',
        lambda m: _wrap(m.group(), _GRAD_START),
        chunk,
    ))

    return s


def _font(size: int, bold: bool = True) -> QFont:
    f = QFont()
    f.setPointSize(size)
    f.setBold(bold)
    return f


class _AccentFrame(QFrame):
    """Card with a blue→purple gradient left accent bar and border."""

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        painter.setBrush(QColor(_BG))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(self.rect()), 12, 12)
        bar_grad = QLinearGradient(0, 16, 0, h - 16)
        bar_grad.setColorAt(0.0, QColor(_GRAD_START))
        bar_grad.setColorAt(1.0, QColor(_GRAD_END))
        painter.setBrush(bar_grad)
        painter.drawRoundedRect(QRectF(0, 16, 4, h - 32), 2, 2)
        border_grad = QLinearGradient(0, 0, 0, h)
        c0 = QColor(_GRAD_START); c0.setAlpha(80)
        c1 = QColor(_GRAD_END);   c1.setAlpha(80)
        border_grad.setColorAt(0.0, c0)
        border_grad.setColorAt(1.0, c1)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_grad, 1))
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, h - 1), 12, 12)


class RecommendationWidget(VectorWidget):
    NAME = 'Recommendation'
    DESCRIPTION = "Portfolio insight and next-step guidance."
    DEFAULT_ROWSPAN = 2
    DEFAULT_COLSPAN = 10

    def __init__(self, window=None, parent=None) -> None:
        super().__init__(window=window, parent=parent)

        self._tw_timer = QTimer(self)
        self._tw_timer.setInterval(10)
        self._tw_timer.timeout.connect(self._tw_step)
        self._tw_plain = ''
        self._tw_html  = ''
        self._tw_pos   = 0

        self.setStyleSheet('background: transparent; border: none;')

        self._card = _AccentFrame(self)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(10)

        title_lbl = QLabel('Recommendation')
        title_lbl.setFont(_font(16, bold=True))
        title_lbl.setStyleSheet('color: #e7ebf3; border: none;')
        card_layout.addWidget(title_lbl)

        self._text_lbl = QLabel('')
        self._text_lbl.setWordWrap(True)
        self._text_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._text_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._text_lbl.setStyleSheet(
            'border: none; color: #e7ebf3; font-size: 20pt; font-weight: 700;'
        )
        card_layout.addStretch(1)
        card_layout.addWidget(self._text_lbl)
        card_layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._card)

    def _fit_pt(self, text: str) -> int:
        """Binary-search the largest pt size where wrapped text fits the label area."""
        # Use label dimensions if laid out, else estimate from card minus chrome
        w = self._text_lbl.width()
        h = self._text_lbl.height()
        if w < 20:
            w = max(self._card.width() - 56, 200)
        if h < 20:
            h = max(self._card.height() - 90, 60)  # subtract title + margins

        for pt in range(22, 9, -1):
            fm = QFontMetrics(_font(pt))
            br = fm.boundingRect(
                QRect(0, 0, w, 10000),
                Qt.TextFlag.TextWordWrap,
                text,
            )
            if br.height() <= h:
                return pt
        return 10

    def _apply_font(self, pt: int) -> None:
        self._text_lbl.setStyleSheet(
            f'border: none; color: #e7ebf3; font-size: {pt}pt; font-weight: 700;'
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._card.setGeometry(self.rect())
        # Re-fit text if not mid-animation
        if self._tw_plain and not self._tw_timer.isActive():
            pt = self._fit_pt(self._tw_plain)
            self._apply_font(pt)
            self._text_lbl.setTextFormat(Qt.TextFormat.RichText)
            self._text_lbl.setText(self._tw_html)
        super().resizeEvent(event)

    def _apply_style(self, edit: bool) -> None:
        border = '#3A8DFF' if edit else 'transparent'
        self.setStyleSheet(
            f'background: transparent; border: 2px solid {border}; border-radius: 12px;'
        )

    def _tw_step(self) -> None:
        self._tw_pos += 1
        self._text_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self._text_lbl.setText(self._tw_plain[:self._tw_pos])
        if self._tw_pos >= len(self._tw_plain):
            self._tw_timer.stop()
            # Snap to highlighted HTML at fitted size
            pt = self._fit_pt(self._tw_plain)
            self._apply_font(pt)
            self._text_lbl.setTextFormat(Qt.TextFormat.RichText)
            self._text_lbl.setText(self._tw_html)

    def _start_typewrite(self, plain: str) -> None:
        self._tw_timer.stop()
        self._tw_plain = plain
        self._tw_html  = _highlight_html(plain)
        self._tw_pos   = 0
        pt = self._fit_pt(plain)
        self._text_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self._apply_font(pt)
        self._text_lbl.setText('')
        self._tw_timer.start()

    def refresh(self) -> None:
        if not self._window:
            return

        positions = self._window.positions or []
        store     = self._window.store
        settings  = self._window.settings

        try:
            result = generate_recommendation(positions, store, settings)
            if len(result) == 2:
                text, _color = result
            else:
                s1, s2, _color = result
                text = s1 + "  " + s2
        except Exception:  # noqa: BLE001
            text = "Unable to generate a recommendation right now. Check your positions and try refreshing."

        self._start_typewrite(text)
