from __future__ import annotations

from PySide6.QtWidgets import QProgressBar, QWidget


class ASProgressBar(QProgressBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASProgress")
        self.setTextVisible(True)
