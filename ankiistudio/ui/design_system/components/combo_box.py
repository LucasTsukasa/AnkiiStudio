from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget


class ASComboBox(QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASComboBox")
