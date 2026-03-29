from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..widgets import CardFrame

if TYPE_CHECKING:
    from vector.app import VectorMainWindow


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
        avatar.setStyleSheet('font-size: 42pt;')
        text_container = QVBoxLayout()
        name = QLabel('Guest User')
        name.setStyleSheet('font-size: 24pt; font-weight: 700;')
        text_container.addWidget(QLabel('Guest Profile'))
        text_container.addWidget(name)
        text_container.addWidget(self.member_since)
        hero_layout.addWidget(avatar)
        hero_layout.addLayout(text_container)
        hero_layout.addStretch(1)
        hero_layout.addWidget(self.total_value)
        self.total_value.setStyleSheet('font-size: 30pt; font-weight: 700;')
        layout.addWidget(hero)
        layout.addStretch(1)

    def update_profile(self, state: dict[str, Any], positions: list[dict[str, Any]], analytics: dict[str, Any]) -> None:
        self.member_since.setText(f"Member since: {self.window.format_date(state.get('first_launch_date'))}")
        self.total_value.setText(self.window.format_currency(analytics['portfolio_value']))
