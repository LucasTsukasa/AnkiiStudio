from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget


class ASTabWidget(QTabWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASTabs")
        self.setDocumentMode(True)
