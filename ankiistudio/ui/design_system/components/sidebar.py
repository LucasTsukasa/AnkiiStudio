from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QWidget

from .button import ASButton


class ASSidebar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASSidebar")


class ASSidebarItem(ASButton):
    def __init__(self, text: str = "", parent: QWidget | None = None, *, icon: QIcon | None = None) -> None:
        super().__init__(text, parent, variant="ghost")
        self.setObjectName("ASSidebarItem")
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon is not None:
            self.setIcon(icon)
            self.setIconSize(QSize(18, 18))
