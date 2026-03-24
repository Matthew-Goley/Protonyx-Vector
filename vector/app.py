from __future__ import annotations

import sys
from datetime import datetime
from functools import partial
from typing import Any

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QTimer, Qt
from PyQt6.QtGui import QAction, QColor, QDoubleValidator, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .analytics import compute_portfolio_analytics
from .constants import APP_NAME, APP_VERSION, COMPANY_NAME, LOGO_PATH, TASKBAR_LOGO_PATH, VOLATILITY_LOOKBACK_PERIODS
from .store import DataStore
from .widget_registry import discover_widgets, get_widget_class
from .widgets import BlurrableStack, CardFrame, DimOverlay, EmptyState, GradientBorderFrame, GradientLine, LoadingButton


DARK_STYLESHEET = """
QWidget {
    background-color: #0b1020;
    color: #e7ebf3;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #0b1020;
}
QPushButton {
    background: #1a2334;
    border: 1px solid #2c364a;
    border-radius: 12px;
    padding: 10px 16px;
}
QPushButton:hover { background: #202b41; }
QPushButton:pressed { background: #121929; }
QPushButton[accent='true'] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3A8DFF, stop:1 #B44AE6);
    color: #ffffff;
    border: none;
    font-weight: 600;
}
QPushButton[accent='true']:disabled {
    background: #1e3a6e;
    color: #6a8fc4;
}
QLineEdit, QComboBox, QListWidget, QSpinBox, QTableWidget {
    background: #121828;
    border: 1px solid #2c364a;
    border-radius: 10px;
    padding: 8px;
}
QHeaderView::section {
    background: #121828;
    color: #9aa7be;
    border: none;
    padding: 8px;
}
QTableWidget {
    gridline-color: #243046;
}
QScrollArea { border: none; }
QLabel { background: transparent; }
QFrame#cardFrame {
    background: #161b26;
    border: 1px solid #2a3142;
    border-radius: 16px;
}
QFrame#sidebarFrame {
    background: #0f1526;
    border: none;
}
QFrame#vectorWidget {
    background: #121828;
    border: 1px solid #2c364a;
    border-radius: 12px;
}
QFrame#vectorWidget[editing="true"] { border-color: #3A8DFF; }
QPushButton#navButton {
    background: transparent;
    border: 1px solid transparent;
    text-align: left;
    padding-left: 16px;
}
QPushButton#navButton:hover { background: #1a2336; border-color: transparent; }
QPushButton#navButton[active="true"] {
    background: #151e30;
    border: 1px solid #2d3c58;
}
QLabel#headerBreadcrumb { color: #90a0bb; }
"""

LIGHT_STYLESHEET = """
QWidget {
    background-color: #f4f7fb;
    color: #182233;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog { background-color: #f4f7fb; }
QPushButton {
    background: white;
    border: 1px solid #ccd5e5;
    border-radius: 12px;
    padding: 10px 16px;
}
QPushButton[accent='true'] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3A8DFF, stop:1 #B44AE6);
    color: #ffffff;
    border: none;
    font-weight: 600;
}
QLineEdit, QComboBox, QListWidget, QSpinBox, QTableWidget {
    background: white;
    border: 1px solid #ccd5e5;
    border-radius: 10px;
    padding: 8px;
}
QHeaderView::section {
    background: white;
    color: #536075;
    border: none;
    padding: 8px;
}
QTableWidget {
    gridline-color: #dde4f0;
}
QScrollArea { border: none; }
QLabel { background: transparent; }
QFrame#cardFrame {
    background: #ffffff;
    border: 1px solid #e2e8f4;
    border-radius: 16px;
}
QFrame#sidebarFrame {
    background: #ffffff;
    border: none;
}
QFrame#vectorWidget {
    background: #f8faff;
    border: 1px solid #ccd5e5;
    border-radius: 12px;
}
QFrame#vectorWidget[editing="true"] { border-color: #3A8DFF; }
QPushButton#navButton {
    background: transparent;
    border: 1px solid transparent;
    text-align: left;
    padding-left: 16px;
}
QPushButton#navButton:hover { background: #edf0f8; border-color: transparent; }
QPushButton#navButton[active="true"] {
    background: #e8edf7;
    border: 1px solid #c5d0e8;
}
QLabel#headerBreadcrumb { color: #536075; }
"""


class PositionDialog(QDialog):
    def __init__(self, store: DataStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.position_data: dict[str, Any] | None = None
        self.setModal(True)
        self.setWindowTitle('Add Position')
        self.setMinimumWidth(380)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel('Add a portfolio position')
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        subtitle = QLabel('Vector will validate the ticker with Yahoo Finance before saving it.')
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet('color: #8d98af;')
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText('AAPL')
        self.ticker_input.textChanged.connect(self._uppercase_ticker)
        self.shares_input = QLineEdit()
        self.shares_input.setValidator(QDoubleValidator(0.0, 10_000_000.0, 4, self))
        self.shares_input.setPlaceholderText('10')
        form.addRow('Ticker Symbol', self.ticker_input)
        form.addRow('Number of Shares', self.shares_input)
        layout.addLayout(form)

        self.error_label = QLabel('')
        self.error_label.setStyleSheet('color: #ff6b6b;')
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.submit_button = LoadingButton('Validate & Add')
        self.submit_button.setProperty('accent', True)
        self.submit_button.clicked.connect(self.submit)
        buttons.addButton(self.submit_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _uppercase_ticker(self, text: str) -> None:
        cursor = self.ticker_input.cursorPosition()
        self.ticker_input.blockSignals(True)
        self.ticker_input.setText(text.upper())
        self.ticker_input.setCursorPosition(cursor)
        self.ticker_input.blockSignals(False)

    def submit(self) -> None:
        ticker = self.ticker_input.text().strip().upper()
        shares_text = self.shares_input.text().strip()
        if not ticker or not shares_text:
            self.error_label.setText('Please enter a ticker and a share count.')
            return
        shares = float(shares_text)
        if shares <= 0:
            self.error_label.setText('Shares must be greater than zero.')
            return
        self.submit_button.start_loading('Validating...')
        self.error_label.setText('')
        QApplication.processEvents()
        try:
            snapshot = self.store.validate_ticker(ticker)
        except Exception as exc:  # noqa: BLE001
            self.submit_button.stop_loading('Validate & Add')
            self.error_label.setText(str(exc))
            return
        self.submit_button.stop_loading('Validate & Add')
        self.position_data = {
            'ticker': snapshot['ticker'],
            'shares': shares,
            'current_price': snapshot['price'],
            'equity': shares * snapshot['price'],
            'sector': snapshot['sector'],
            'name': snapshot['name'],
        }
        self.accept()


class PositionCard(CardFrame):
    def __init__(self, position: dict[str, Any], currency_formatter, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        ticker = QLabel(position['ticker'])
        ticker_font = QFont()
        ticker_font.setPointSize(18)
        ticker_font.setBold(True)
        ticker.setFont(ticker_font)
        layout.addWidget(ticker)
        for label, value in (
            ('Shares', f"{position['shares']:.4f}".rstrip('0').rstrip('.')),
            ('Current Price', currency_formatter(position['current_price'])),
            ('Equity', currency_formatter(position['equity'])),
            ('Sector', position.get('sector', 'Unknown')),
        ):
            row = QLabel(f'<b>{label}:</b> {value}')
            row.setWordWrap(True)
            layout.addWidget(row)
        layout.addStretch(1)
        self.setFixedWidth(220)


class OnboardingPage(QWidget):
    def __init__(self, window: 'VectorMainWindow') -> None:
        super().__init__()
        self.window = window
        self.pending_positions: list[dict[str, Any]] = []
        self.cards_layout: QHBoxLayout | None = None
        self.launch_button: QPushButton | None = None
        self.overlay: DimOverlay | None = None
        self.blur_wrapper: BlurrableStack | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.setSpacing(16)

        content = QWidget()
        self.blur_wrapper = BlurrableStack(content, self)
        self.overlay = DimOverlay(self)
        outer.addWidget(self.blur_wrapper)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Use a scroll area so content is never clipped on small windows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(20)
        inner_layout.addStretch(1)

        title = QLabel(f'Welcome to {APP_NAME}')
        title_font = QFont()
        title_font.setPointSize(26)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel(
            f'{COMPANY_NAME} {APP_NAME} needs your first positions to begin tracking portfolio analytics. Add one or more holdings to get started.'
        )
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setMaximumWidth(720)
        subtitle.setMinimumHeight(48)
        subtitle.setStyleSheet('color: #90a0bb;')
        inner_layout.addWidget(title)
        inner_layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignHCenter)

        add_button = LoadingButton('Add Position')
        add_button.setProperty('accent', True)
        add_button.setFixedWidth(180)
        add_button.clicked.connect(self.open_add_modal)
        inner_layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setMinimumHeight(250)
        self.cards_container = QWidget()
        self.cards_layout = QHBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(8, 8, 8, 8)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addWidget(EmptyState('No positions yet', 'Add at least one validated holding to unlock the portfolio dashboard.'))
        cards_scroll.setWidget(self.cards_container)
        inner_layout.addWidget(cards_scroll)

        self.launch_button = LoadingButton('Launch Portfolio')
        self.launch_button.setProperty('accent', True)
        self.launch_button.setEnabled(False)
        self.launch_button.setFixedWidth(220)
        self.launch_button.clicked.connect(self.launch)
        inner_layout.addWidget(self.launch_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        inner_layout.addStretch(1)

        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def resizeEvent(self, event) -> None:  # noqa: N802
        if self.overlay:
            self.overlay.sync_geometry()
        super().resizeEvent(event)

    def open_add_modal(self) -> None:
        if self.blur_wrapper and self.overlay:
            self.blur_wrapper.set_blurred(True)
            self.overlay.show()
        dialog = PositionDialog(self.window.store, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted and dialog.position_data
        if accepted:
            self.pending_positions.append(dialog.position_data)
        if self.blur_wrapper and self.overlay:
            self.blur_wrapper.set_blurred(False)
            self.overlay.hide()
        if accepted:
            self.refresh_cards()

    def refresh_cards(self) -> None:
        if not self.cards_layout or not self.launch_button:
            return
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not self.pending_positions:
            self.cards_layout.addWidget(EmptyState('No positions yet', 'Add at least one validated holding to unlock the portfolio dashboard.'))
        for position in self.pending_positions:
            self.cards_layout.addWidget(PositionCard(position, self.window.format_currency))
        self.cards_layout.addStretch(1)
        self.launch_button.setEnabled(bool(self.pending_positions))
        # Force the container and layout to recalculate geometry
        self.cards_container.adjustSize()
        self.cards_container.updateGeometry()
        self.cards_container.update()

    def launch(self) -> None:
        self.launch_button.start_loading('Launching...')
        QApplication.processEvents()
        self.window.positions = list(self.pending_positions)
        self.window.store.save_positions(self.window.positions)
        state = self.window.store.load_app_state()
        state['onboarding_complete'] = True
        self.window.store.save_app_state(state)
        self.window.load_main_shell()


# Grid constants
# Toolbar (col 0) = _UNIT px wide. Content grid = 10 cols.
# Total = _UNIT + _GAP + _CONTENT_W = 90 + 10 + 990 = 1090 px,
# which fits the 1092 px available at minimum window size.
_UNIT         = 90              # one grid unit in px
_GAP          = 10              # gap between units
_CELL         = _UNIT + _GAP   # 100 px — step per cell
_GRID_COLS    = 11
_CONTENT_COLS = _GRID_COLS                  # all 11 cols usable
_CONTENT_W    = _CONTENT_COLS * _CELL - _GAP  # 1090 px


# ---------------------------------------------------------------------------
# _SnapIndicator — ghost overlay shown while dragging
# ---------------------------------------------------------------------------

class _SnapIndicator(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(58, 141, 255, 30))
        pen = QPen(QColor(58, 141, 255, 160))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)
        painter.end()


# Widget types live in vector/widget_types/ — see vector/widget_base.py


# ---------------------------------------------------------------------------
# DashboardGrid — absolute-positioned content area (cols 1-10)
# ---------------------------------------------------------------------------

class DashboardGrid(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(_CONTENT_W)
        self._items: list[dict] = []
        self._snap = _SnapIndicator(self)
        self._edit_mode = False
        self.resize(_CONTENT_W, _CELL)

    # -- geometry helpers --------------------------------------------------

    @staticmethod
    def _cell_rect(row: int, col: int, rowspan: int = 1, colspan: int = 1) -> QRect:
        return QRect(
            col * _CELL,
            row * _CELL,
            colspan * _UNIT + max(0, colspan - 1) * _GAP,
            rowspan * _UNIT + max(0, rowspan - 1) * _GAP,
        )

    @staticmethod
    def _nearest_cell(pos: QPoint, colspan: int = 1) -> tuple[int, int]:
        col = max(0, min(_CONTENT_COLS - colspan, round(pos.x() / _CELL)))
        row = max(0, round(pos.y() / _CELL))
        return row, col

    def _refresh_height(self) -> None:
        max_bottom = max((i['row'] + i['rowspan'] for i in self._items), default=1)
        self.resize(_CONTENT_W, max_bottom * _CELL + _GAP)

    # -- public API --------------------------------------------------------

    def add_widget(self, widget: QWidget, row: int, col: int,
                   rowspan: int = 1, colspan: int = 1,
                   fixed: bool = False) -> None:
        widget.setParent(self)
        widget.setGeometry(self._cell_rect(row, col, rowspan, colspan))
        widget.show()
        self._items.append({'widget': widget, 'row': row, 'col': col,
                            'rowspan': rowspan, 'colspan': colspan,
                            'fixed': fixed})
        self._refresh_height()

    def _occupied_cells(self, exclude: QWidget | None = None) -> set[tuple[int, int]]:
        occupied: set[tuple[int, int]] = set()
        for i in self._items:
            if i['widget'] is exclude:
                continue
            for r in range(i['row'], i['row'] + i['rowspan']):
                for c in range(i['col'], i['col'] + i['colspan']):
                    occupied.add((r, c))
        return occupied

    def _find_nearest_free(self, row: int, col: int, rowspan: int, colspan: int,
                           exclude: QWidget | None = None) -> tuple[int, int]:
        occupied = self._occupied_cells(exclude)

        def fits(r: int, c: int) -> bool:
            if c < 0 or c + colspan > _CONTENT_COLS or r < 0:
                return False
            return all((r + dr, c + dc) not in occupied
                       for dr in range(rowspan) for dc in range(colspan))

        if fits(row, col):
            return row, col
        for radius in range(1, 60):
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if fits(row + dr, col + dc):
                        return row + dr, col + dc
        return 0, 0

    def next_free_cell(self, rowspan: int = 1, colspan: int = 1) -> tuple[int, int]:
        occupied = self._occupied_cells()

        def fits(r: int, c: int) -> bool:
            if c + colspan > _CONTENT_COLS:
                return False
            return all((r + dr, c + dc) not in occupied
                       for dr in range(rowspan) for dc in range(colspan))

        for row in range(50):
            for col in range(_CONTENT_COLS):
                if fits(row, col):
                    return row, col
        return 0, 0

    def get_layout(self) -> list[dict]:
        """Return serializable layout for all non-fixed widgets."""
        return [
            {
                'type': type(i['widget']).__name__,
                'row': i['row'], 'col': i['col'],
                'rowspan': i['rowspan'], 'colspan': i['colspan'],
            }
            for i in self._items if not i.get('fixed')
        ]

    def restore_layout(self, layout: list[dict], window) -> None:
        """Instantiate and place widgets from a saved layout list."""
        for entry in layout:
            cls = get_widget_class(entry['type'])
            if cls is None:
                continue
            widget = cls(window=window)
            widget.refresh()
            if self._edit_mode:
                widget.set_edit_mode(True)
            self.add_widget(widget, entry['row'], entry['col'],
                            entry['rowspan'], entry['colspan'])

    def remove_widget(self, widget: QWidget) -> None:
        self._items = [i for i in self._items if i['widget'] is not widget]
        widget.setParent(None)
        widget.deleteLater()
        self._refresh_height()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        for item in self._items:
            if item.get('fixed'):
                continue
            w = item['widget']
            if hasattr(w, 'set_edit_mode'):
                w.set_edit_mode(enabled)
        if not enabled:
            self._snap.hide()

    # -- drag callbacks ----------------------------------------------------

    def _on_drag_move(self, widget: QWidget) -> None:
        item = next((i for i in self._items if i['widget'] is widget), None)
        if not item:
            return
        row, col = self._nearest_cell(widget.pos(), item['colspan'])
        # expand grid temporarily so snap indicator is always visible
        needed_h = (row + item['rowspan']) * _CELL + _GAP
        if needed_h > self.height():
            self.resize(_CONTENT_W, needed_h)
        self._snap.setGeometry(self._cell_rect(row, col, item['rowspan'], item['colspan']))
        self._snap.show()
        self._snap.raise_()

    def _on_drag_release(self, widget: QWidget) -> None:
        item = next((i for i in self._items if i['widget'] is widget), None)
        if not item:
            return
        row, col = self._nearest_cell(widget.pos(), item['colspan'])
        row, col = self._find_nearest_free(row, col, item['rowspan'], item['colspan'],
                                           exclude=widget)
        item['row'], item['col'] = row, col
        target = self._cell_rect(row, col, item['rowspan'], item['colspan'])
        anim = QPropertyAnimation(widget, b'geometry', self)
        anim.setDuration(140)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setEndValue(target)
        anim.start()
        self._snap.hide()
        self._refresh_height()


# ---------------------------------------------------------------------------
# _PickerCard — clickable widget-type card inside WidgetPickerDialog
# ---------------------------------------------------------------------------

class _PickerCard(QFrame):
    def __init__(self, name: str, description: str,
                 on_click, featured: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_click = on_click
        self._featured = featured
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)
        name_lbl = QLabel(name)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(11)
        name_lbl.setFont(name_font)
        name_lbl.setFixedWidth(160)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet('color: #8d98af; font-size: 11px;')
        layout.addWidget(name_lbl)
        layout.addWidget(desc_lbl, stretch=1)
        self._set_style(False)

    def _set_style(self, hovered: bool) -> None:
        if self._featured:
            border = '#3A8DFF' if not hovered else '#6aaaff'
            bg = '#131e35' if hovered else '#0f1a2e'
        else:
            border = '#3A8DFF' if hovered else '#2c364a'
            bg = '#151e30' if hovered else '#121828'
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: {'2px' if self._featured else '1px'} solid {border};
                border-radius: 12px;
            }}
        """)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._set_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._set_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# WidgetPickerDialog
# ---------------------------------------------------------------------------

class WidgetPickerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chosen_class: type | None = None
        self.setModal(True)
        self.setWindowTitle('Add Widget')
        self.setMinimumWidth(440)
        main_win = QApplication.activeWindow()
        if main_win is not None:
            self.setMaximumWidth(main_win.width())
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        title = QLabel('Choose a widget')
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        sub = QLabel('Select the widget you want to add to your dashboard.')
        sub.setStyleSheet('color: #8d98af;')
        sub.setWordWrap(True)
        layout.addWidget(sub)
        cards_col = QVBoxLayout()
        cards_col.setSpacing(8)
        from vector.widget_types.recommendation import RecommendationWidget as _RW
        for cls in discover_widgets():
            cards_col.addWidget(_PickerCard(
                cls.NAME, cls.DESCRIPTION,
                lambda c=cls: self._pick(c),
                featured=(cls is _RW),
            ))
        layout.addLayout(cards_col)
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignRight)

    def _pick(self, cls: type) -> None:
        self.chosen_class = cls
        self.accept()


# ---------------------------------------------------------------------------
# DashboardPage
# ---------------------------------------------------------------------------

def _circle_btn_style(font_size: int, active: bool = False) -> str:
    if active:
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5aa3ff, stop:1 #c96df0);
                color: #ffffff;
                font-size: {font_size}px;
                font-weight: 700;
                border: 2px solid rgba(255,255,255,0.45);
                border-radius: 32px;
            }}
        """
    return f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #3A8DFF, stop:1 #B44AE6);
            color: #ffffff;
            font-size: {font_size}px;
            font-weight: 300;
            border: none;
            border-radius: 32px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #5aa3ff, stop:1 #c96df0);
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #2a7aee, stop:1 #9a3ad4);
        }}
    """


_DEFAULT_LAYOUT = [
    {'type': 'RecommendationWidget',      'row': 0, 'col': 1,  'rowspan': 2, 'colspan': 10},
    {'type': 'PortfolioVectorWidget',     'row': 2, 'col': 5,  'rowspan': 3, 'colspan': 6},
    {'type': 'PositionsListWidget',       'row': 2, 'col': 0,  'rowspan': 3, 'colspan': 5},
    {'type': 'TotalEquityWidget',         'row': 5, 'col': 0,  'rowspan': 2, 'colspan': 4},
    {'type': 'PortfolioVolatilityWidget', 'row': 5, 'col': 4,  'rowspan': 2, 'colspan': 4},
]


class DashboardPage(QWidget):
    def __init__(self, window: 'VectorMainWindow') -> None:
        super().__init__()
        self.window = window
        self._edit_mode = False
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        # Full 11-col grid — col 0 holds fixed buttons, cols 1-10 are free
        self._dash_grid = DashboardGrid()

        self._add_btn = QPushButton('+')
        self._add_btn.setFixedSize(64, 64)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet(_circle_btn_style(28))
        self._add_btn.clicked.connect(self._open_picker)

        self._edit_btn = QPushButton('Edit')
        self._edit_btn.setFixedSize(64, 64)
        self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_btn.setStyleSheet(_circle_btn_style(13))
        self._edit_btn.clicked.connect(self._toggle_edit_mode)

        # Place buttons at fixed positions in col 0 — they cannot be moved
        self._dash_grid.add_widget(self._add_btn, row=0, col=0, fixed=True)
        self._dash_grid.add_widget(self._edit_btn, row=1, col=0, fixed=True)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._dash_grid)
        self._scroll.setWidgetResizable(False)
        self._scroll.setFixedWidth(_CONTENT_W)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        row.addWidget(self._scroll)
        row.addStretch(1)

        outer.addLayout(row, stretch=1)  # row fills all available height

        # Load saved layout, or apply default on first run
        saved = self.window.store.load_layout()
        self._dash_grid.restore_layout(saved if saved else _DEFAULT_LAYOUT, self.window)

    def save_layout(self) -> None:
        self.window.store.save_layout(self._dash_grid.get_layout())

    def _open_picker(self) -> None:
        dialog = WidgetPickerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.chosen_class:
            cls = dialog.chosen_class
            widget = cls(window=self.window)
            widget.refresh()
            if self._edit_mode:
                widget.set_edit_mode(True)
            row, col = self._dash_grid.next_free_cell(cls.DEFAULT_ROWSPAN, cls.DEFAULT_COLSPAN)
            self._dash_grid.add_widget(widget, row, col,
                                       rowspan=cls.DEFAULT_ROWSPAN,
                                       colspan=cls.DEFAULT_COLSPAN)

    def _toggle_edit_mode(self) -> None:
        self._edit_mode = not self._edit_mode
        self._dash_grid.set_edit_mode(self._edit_mode)
        self._edit_btn.setStyleSheet(_circle_btn_style(13, active=self._edit_mode))

    def update_dashboard(self, positions: list[dict[str, Any]], analytics: dict[str, Any]) -> None:
        for item in self._dash_grid._items:
            w = item['widget']
            if hasattr(w, 'refresh'):
                w.refresh()


class ProfilePage(QWidget):
    def __init__(self, window: 'VectorMainWindow') -> None:
        super().__init__()
        self.window = window
        self.member_since = QLabel('—')
        self.total_value = QLabel('$0.00')
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        hero = CardFrame()
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        avatar = QLabel('👤')
        avatar.setStyleSheet('font-size: 42px;')
        text_container = QVBoxLayout()
        name = QLabel('Guest User')
        name.setStyleSheet('font-size: 24px; font-weight: 700;')
        text_container.addWidget(QLabel('Guest Profile'))
        text_container.addWidget(name)
        text_container.addWidget(self.member_since)
        hero_layout.addWidget(avatar)
        hero_layout.addLayout(text_container)
        hero_layout.addStretch(1)
        hero_layout.addWidget(self.total_value)
        self.total_value.setStyleSheet('font-size: 30px; font-weight: 700;')
        layout.addWidget(hero)
        layout.addStretch(1)

    def update_profile(self, state: dict[str, Any], positions: list[dict[str, Any]], analytics: dict[str, Any]) -> None:
        self.member_since.setText(f"Member since: {self.window.format_date(state.get('first_launch_date'))}")
        self.total_value.setText(self.window.format_currency(analytics['portfolio_value']))


class SettingsPage(QWidget):
    def __init__(self, window: 'VectorMainWindow') -> None:
        super().__init__()
        self.window = window
        self.remove_list = QListWidget()
        self._build_ui()

    def _add_section(self, parent: QVBoxLayout, title: str) -> QFormLayout:
        card = CardFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        heading = QLabel(title)
        heading.setStyleSheet('font-size: 16px; font-weight: 700;')
        layout.addWidget(heading)
        form = QFormLayout()
        form.setSpacing(12)
        layout.addLayout(form)
        parent.addWidget(card)
        return form

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        general = self._add_section(layout, 'General')
        self.theme_combo = QComboBox(); self.theme_combo.addItems(['Dark', 'Light'])
        self.currency_combo = QComboBox(); self.currency_combo.addItems(['USD', 'EUR', 'GBP'])
        self.date_combo = QComboBox(); self.date_combo.addItems(['MM/DD/YYYY', 'DD/MM/YYYY'])
        general.addRow('Theme', self.theme_combo)
        general.addRow('Default Currency', self.currency_combo)
        general.addRow('Date Format', self.date_combo)

        refresh = self._add_section(layout, 'Data & Refresh')
        self.refresh_combo = QComboBox(); self.refresh_combo.addItems(['1 min', '5 min', '15 min', 'Manual only'])
        clear_cache_button = LoadingButton('Clear Cached Price Data')
        clear_cache_button.clicked.connect(self.window.clear_cache)
        reset_button = LoadingButton('Reset All App Data / Re-run Onboarding')
        reset_button.clicked.connect(self.window.reset_all_data)
        refresh.addRow('Auto-refresh Interval', self.refresh_combo)
        refresh.addRow('', clear_cache_button)
        refresh.addRow('', reset_button)

        thresholds = self._add_section(layout, 'Portfolio Direction Thresholds')
        self.strong_spin = self._spin_box(); self.strong_spin.setRange(-100, 100)
        self.steady_spin = self._spin_box(); self.steady_spin.setRange(-100, 100)
        self.neutral_low_spin = self._spin_box(); self.neutral_low_spin.setRange(-100, 100)
        self.neutral_high_spin = self._spin_box(); self.neutral_high_spin.setRange(-100, 100)
        self.depreciating_spin = self._spin_box(); self.depreciating_spin.setRange(-100, 100)
        thresholds.addRow('Strong cutoff (%)', self.strong_spin)
        thresholds.addRow('Steady cutoff (%)', self.steady_spin)
        thresholds.addRow('Neutral low (%)', self.neutral_low_spin)
        thresholds.addRow('Neutral high (%)', self.neutral_high_spin)
        thresholds.addRow('Weak cutoff (%)', self.depreciating_spin)

        volatility = self._add_section(layout, 'Volatility')
        self.lookback_combo = QComboBox(); self.lookback_combo.addItems(['3 months', '6 months', '1 year'])
        self.low_vol_spin = QSpinBox(); self.low_vol_spin.setRange(1, 100)
        self.high_vol_spin = QSpinBox(); self.high_vol_spin.setRange(1, 100)
        volatility.addRow('Lookback Period', self.lookback_combo)
        volatility.addRow('Low cutoff', self.low_vol_spin)
        volatility.addRow('High cutoff', self.high_vol_spin)

        positions = self._add_section(layout, 'Positions')
        add_position = LoadingButton('Add New Position')
        add_position.clicked.connect(self.window.add_position_from_settings)
        remove_button = LoadingButton('Remove Selected Position')
        remove_button.clicked.connect(self.remove_selected_position)
        positions.addRow('', add_position)
        positions.addRow('Current Positions', self.remove_list)
        positions.addRow('', remove_button)

        about = self._add_section(layout, 'About')
        about.addRow('App Version', QLabel(APP_VERSION))
        about.addRow('Brand', QLabel(f'{COMPANY_NAME} / {APP_NAME}'))
        about.addRow('Credits', QLabel('PyQt6, Yahoo Finance (yfinance)'))

        self.save_button = LoadingButton('Save Settings')
        self.save_button.setProperty('accent', True)
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _spin_box(self) -> QDoubleSpinBoxCompat:
        return QDoubleSpinBoxCompat()

    def load_from_settings(self, settings: dict[str, Any], positions: list[dict[str, Any]]) -> None:
        self.theme_combo.setCurrentText(settings['theme'])
        self.currency_combo.setCurrentText(settings['currency'])
        self.date_combo.setCurrentText(settings['date_format'])
        self.refresh_combo.setCurrentText(settings['refresh_interval'])
        thresholds = settings['direction_thresholds']
        self.strong_spin.setValue(float(thresholds['strong']))
        self.steady_spin.setValue(float(thresholds['steady']))
        self.neutral_low_spin.setValue(float(thresholds['neutral_low']))
        self.neutral_high_spin.setValue(float(thresholds['neutral_high']))
        self.depreciating_spin.setValue(float(thresholds['depreciating']))
        vol = settings['volatility']
        self.lookback_combo.setCurrentText(vol['lookback'])
        self.low_vol_spin.setValue(int(vol['low_cutoff']))
        self.high_vol_spin.setValue(int(vol['high_cutoff']))
        self.remove_list.clear()
        for position in positions:
            item = QListWidgetItem(f"{position['ticker']} — {position['shares']:.4f}".rstrip('0').rstrip('.'))
            item.setData(Qt.ItemDataRole.UserRole, position['ticker'])
            self.remove_list.addItem(item)

    def save_settings(self) -> None:
        self.save_button.start_loading('Saving...')
        QApplication.processEvents()
        settings = self.window.settings
        settings['theme'] = self.theme_combo.currentText()
        settings['currency'] = self.currency_combo.currentText()
        settings['date_format'] = self.date_combo.currentText()
        settings['refresh_interval'] = self.refresh_combo.currentText()
        settings['direction_thresholds'] = {
            'strong': self.strong_spin.value(),
            'steady': self.steady_spin.value(),
            'neutral_low': self.neutral_low_spin.value(),
            'neutral_high': self.neutral_high_spin.value(),
            'depreciating': self.depreciating_spin.value(),
        }
        settings['volatility'] = {
            'lookback': self.lookback_combo.currentText(),
            'lookback_period': VOLATILITY_LOOKBACK_PERIODS[self.lookback_combo.currentText()],
            'low_cutoff': self.low_vol_spin.value(),
            'high_cutoff': self.high_vol_spin.value(),
        }
        self.window.settings = settings
        self.window.store.save_settings(settings)
        self.window.apply_theme()
        self.window.refresh_data()
        self.save_button.stop_loading('Save Settings')

    def remove_selected_position(self) -> None:
        item = self.remove_list.currentItem()
        if not item:
            return
        ticker = item.data(Qt.ItemDataRole.UserRole)
        confirm = QMessageBox.question(self, 'Remove Position', f'Remove {ticker} from the portfolio?')
        if confirm == QMessageBox.StandardButton.Yes:
            self.window.positions = [position for position in self.window.positions if position['ticker'] != ticker]
            self.window.store.save_positions(self.window.positions)
            self.window.refresh_data()
            self.load_from_settings(self.window.settings, self.window.positions)


class QDoubleSpinBoxCompat(QSpinBox):
    def __init__(self) -> None:
        super().__init__()
        self.setSingleStep(1)
        self.setRange(-100, 100)
        self.setSuffix('%')

    def value(self) -> float:  # type: ignore[override]
        return super().value() / 100

    def setValue(self, value: float) -> None:  # type: ignore[override]
        super().setValue(int(round(value * 100)))


class MainShell(QWidget):
    def __init__(self, window: 'VectorMainWindow') -> None:
        super().__init__()
        self.window = window
        self.sidebar_buttons: dict[str, QPushButton] = {}
        self.page_stack = QStackedWidget()
        self.header_title = QLabel('Dashboard')
        self.header_breadcrumb = QLabel('Vector / Dashboard')
        self.dashboard_page = DashboardPage(window)
        self.profile_page = ProfilePage(window)
        self.settings_page = SettingsPage(window)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName('sidebarFrame')
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 24, 20, 24)
        sidebar_layout.setSpacing(12)
        sidebar_layout.addWidget(self.window.make_logo_label(44))
        for name in ('Dashboard', 'Profile', 'Settings'):
            button = QPushButton(name)
            button.setObjectName('navButton')
            button.clicked.connect(partial(self.set_page, name))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            sidebar_layout.addWidget(button)
            self.sidebar_buttons[name] = button
        sidebar_layout.addStretch(1)
        root.addWidget(sidebar)
        root.addWidget(GradientLine())

        content = QVBoxLayout()
        content.setContentsMargins(24, 24, 24, 24)
        content.setSpacing(18)

        header = GradientBorderFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 18, 20, 18)
        text_col = QVBoxLayout()
        self.header_title.setStyleSheet('font-size: 22px; font-weight: 700;')
        self.header_breadcrumb.setObjectName('headerBreadcrumb')
        text_col.addWidget(self.header_title)
        text_col.addWidget(self.header_breadcrumb)
        header_layout.addLayout(text_col)
        header_layout.addStretch(1)
        content.addWidget(header)

        self.page_stack.addWidget(self.dashboard_page)
        self.page_stack.addWidget(self.profile_page)
        self.page_stack.addWidget(self.settings_page)
        content.addWidget(self.page_stack, stretch=1)
        content_wrapper = QWidget()
        content_wrapper.setLayout(content)
        root.addWidget(content_wrapper, stretch=1)
        self.set_page('Dashboard')

    def set_page(self, page_name: str) -> None:
        mapping = {'Dashboard': 0, 'Profile': 1, 'Settings': 2}
        self.page_stack.setCurrentIndex(mapping[page_name])
        self.header_title.setText(page_name)
        self.header_breadcrumb.setText(f'Vector / {page_name}')
        for name, button in self.sidebar_buttons.items():
            button.setProperty('active', 'true' if name == page_name else 'false')
            button.style().unpolish(button)
            button.style().polish(button)
        if page_name == 'Dashboard':
            for item in self.dashboard_page._dash_grid._items:
                w = item['widget']
                if type(w).__name__ == 'RecommendationWidget':
                    w.refresh()


class VectorMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.store = DataStore()
        self.settings = self.store.load_settings()
        self.settings['volatility']['lookback_period'] = VOLATILITY_LOOKBACK_PERIODS.get(self.settings['volatility'].get('lookback', '6 months'), '6mo')
        self.state = self.store.load_app_state()
        self.positions = self.store.load_positions()
        self.shell: MainShell | None = None
        self.setWindowTitle(f'{COMPANY_NAME} {APP_NAME}')
        self.setMinimumSize(1360, 860)
        self.apply_theme()
        self._build_menu()
        if self.state.get('onboarding_complete') and self.positions:
            self.load_main_shell()
        else:
            self.setCentralWidget(OnboardingPage(self))

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.shell:
            self.shell.dashboard_page.save_layout()
        super().closeEvent(event)

    def _build_menu(self) -> None:
        refresh_action = QAction('Refresh Market Data', self)
        refresh_action.triggered.connect(self.refresh_data)
        self.addAction(refresh_action)

    def apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(DARK_STYLESHEET if self.settings.get('theme', 'Dark') == 'Dark' else LIGHT_STYLESHEET)

    def format_currency(self, value: float) -> str:
        symbols = {'USD': '$', 'EUR': '€', 'GBP': '£'}
        code = self.settings.get('currency', 'USD')
        return f"{symbols.get(code, '$')}{value:,.2f}"

    def format_date(self, iso_date: str | None) -> str:
        if not iso_date:
            return '—'
        try:
            parsed = datetime.fromisoformat(iso_date).date()
        except ValueError:
            return iso_date
        if self.settings.get('date_format') == 'DD/MM/YYYY':
            return parsed.strftime('%d/%m/%Y')
        return parsed.strftime('%m/%d/%Y')

    def make_logo_label(self, size: int) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet('background: transparent;')
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        icon_label = QLabel()
        pixmap = QPixmap(str(LOGO_PATH))
        if not pixmap.isNull():
            scaled = pixmap.scaledToHeight(size, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(scaled)
            icon_label.setFixedSize(scaled.size())
            layout.addWidget(icon_label)
        else:
            icon_label.setPixmap(self.create_placeholder_logo(size))
            layout.addWidget(icon_label)
            text = QLabel(APP_NAME)
            text.setStyleSheet('font-size: 20px; font-weight: 700;')
            layout.addWidget(text)
        wrapper.setFixedHeight(size + 4)
        return wrapper

    @staticmethod
    def create_placeholder_logo(size: int) -> QPixmap:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor('#111827'))
        painter.setPen(QColor('#253147'))
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 12, 12)
        path = QPainterPath()
        path.moveTo(size * 0.22, size * 0.24)
        path.lineTo(size * 0.50, size * 0.76)
        path.lineTo(size * 0.78, size * 0.24)
        accent_pen = QPen(QColor('#3A8DFF'))
        accent_pen.setWidth(max(3, size // 12))
        accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        accent_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.strokePath(path, accent_pen)
        painter.end()
        return pixmap

    def load_main_shell(self) -> None:
        self.shell = MainShell(self)
        self.setCentralWidget(self.shell)
        self.refresh_data()
        self._setup_auto_refresh()

    def _setup_auto_refresh(self) -> None:
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        self.refresh_timer = QTimer(self)
        interval = self.settings.get('refresh_interval', '5 min')
        mapping = {'1 min': 60_000, '5 min': 300_000, '15 min': 900_000}
        if interval in mapping:
            self.refresh_timer.timeout.connect(self.refresh_data)
            self.refresh_timer.start(mapping[interval])

    def refresh_data(self) -> None:
        if not self.positions or not self.shell:
            return
        refresh_interval = self.settings.get('refresh_interval', '5 min')
        for position in self.positions:
            try:
                snapshot = self.store.get_snapshot(position['ticker'], refresh_interval)
                position['current_price'] = snapshot['price']
                position['sector'] = snapshot['sector']
                position['equity'] = position['shares'] * position['current_price']
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, 'Refresh Warning', f"Could not refresh {position['ticker']}: {exc}")
        self.store.save_positions(self.positions)
        try:
            histories = self.store.build_histories(
                [position['ticker'] for position in self.positions],
                refresh_interval,
                self.settings['volatility']['lookback'],
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, 'Refresh Warning', f'Could not refresh price history: {exc}')
            histories = {position['ticker']: {'6mo': [], '1mo': [], self.settings['volatility']['lookback_period']: []} for position in self.positions}
        analytics = compute_portfolio_analytics(
            self.positions,
            histories,
            self.settings['direction_thresholds'],
            self.settings['volatility'],
        )
        self.state = self.store.load_app_state()
        self.shell.dashboard_page.update_dashboard(self.positions, analytics)
        self.shell.profile_page.update_profile(self.state, self.positions, analytics)
        self.shell.settings_page.load_from_settings(self.settings, self.positions)
        self._setup_auto_refresh()

    def add_position_from_settings(self) -> None:
        dialog = PositionDialog(self.store, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.position_data:
            self.positions.append(dialog.position_data)
            self.store.save_positions(self.positions)
            self.refresh_data()

    def clear_cache(self) -> None:
        self.store.clear_market_cache()
        QMessageBox.information(self, 'Cache Cleared', 'Cached Yahoo Finance data has been cleared.')

    def reset_all_data(self) -> None:
        confirm = QMessageBox.question(
            self,
            'Reset Vector',
            'This will erase positions, settings, cached data, and show onboarding on next launch. Continue?',
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.store.reset_all_data()
        self.settings = self.store.load_settings()
        self.settings['volatility']['lookback_period'] = VOLATILITY_LOOKBACK_PERIODS.get(self.settings['volatility'].get('lookback', '6 months'), '6mo')
        self.state = self.store.load_app_state()
        self.positions = []
        self.apply_theme()
        self.setCentralWidget(OnboardingPage(self))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    taskbar_pixmap = QPixmap(str(TASKBAR_LOGO_PATH))
    app.setWindowIcon(QIcon(taskbar_pixmap if not taskbar_pixmap.isNull() else VectorMainWindow.create_placeholder_logo(128)))
    window = VectorMainWindow()
    window.show()
    return app.exec()
