from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .card import ASCard


class ASToast(ASCard):
    def __init__(self, text: str, parent: QWidget | None = None, *, kind: str = "info") -> None:
        variant = {"error": "danger", "warning": "warning", "success": "success"}.get(kind, "raised")
        super().__init__(parent, variant=variant)
        self.setObjectName("ASToast")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)


class ASToastManager(QWidget):
    """Empilha notificações independentes; uma não sobrescreve outra."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("ASToastManager")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.hide()

    def show_toast(self, text: str, *, kind: str = "info", timeout_ms: int = 4500) -> ASToast:
        toast = ASToast(text, self, kind=kind)
        self._layout.addWidget(toast)
        self.adjustSize()
        self.show()
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self._remove(toast))
        return toast

    def _remove(self, toast: ASToast) -> None:
        toast.deleteLater()
        self.adjustSize()
        if self._layout.count() <= 1:
            QTimer.singleShot(0, self.hide)
