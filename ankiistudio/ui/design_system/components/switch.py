from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

from ..tokens import get_theme_tokens


class ASSwitch(QAbstractButton):
    """Switch compacto desenhado pelo AnkiiStudio, mantendo foco/teclado do Qt."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASSwitch")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Alternar opção")

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(42, 24)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        app = QApplication.instance()
        theme_name = str(app.property("ankiistudioTheme") if app is not None else "dark")
        tokens = get_theme_tokens(theme_name)
        track = QColor(tokens.primary if self.isChecked() else tokens.border_hover)
        if not self.isEnabled():
            track = QColor(tokens.border)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        rect = self.rect().adjusted(1, 3, -1, -3)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        diameter = rect.height() - 4
        x = rect.right() - diameter - 2 if self.isChecked() else rect.left() + 2
        painter.setBrush(QColor(tokens.primary_text if self.isChecked() else tokens.text_soft))
        painter.drawEllipse(int(x), int(rect.top() + 2), int(diameter), int(diameter))
