from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from vector.widget_base import VectorWidget


class PlaceholderWidget(VectorWidget):
    NAME = 'Placeholder'
    DESCRIPTION = 'A blank resizable card.'
    DEFAULT_ROWSPAN = 2
    DEFAULT_COLSPAN = 2

    def __init__(self, window=None, parent=None) -> None:
        super().__init__(window=window, parent=parent)
        layout = QVBoxLayout(self)
        label = QLabel('Placeholder')
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet('color: #4a5568; font-size: 13px; border: none;')
        layout.addWidget(label)
