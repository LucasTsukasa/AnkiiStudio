from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .card import ASCard


class ASSectionCard(ASCard):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASSectionCard")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(18, 16, 18, 16)
        self.root.setSpacing(12)
        if title:
            title_label = QLabel(title)
            title_label.setProperty("asTextRole", "section")
            self.root.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setProperty("asTextRole", "muted")
            subtitle_label.setWordWrap(True)
            self.root.addWidget(subtitle_label)


class ASPageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASPageHeader")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setProperty("asTextRole", "title")
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setProperty("asTextRole", "muted")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)
