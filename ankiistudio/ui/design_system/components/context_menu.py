from __future__ import annotations

from PySide6.QtWidgets import QMenu, QWidget


class ASContextMenu(QMenu):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASContextMenu")
