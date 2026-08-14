from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QTextEdit, QWidget


class _InputStateMixin:
    def set_error(self, enabled: bool, message: str = "") -> None:
        self.setProperty("asError", bool(enabled))
        if enabled and message:
            self.setToolTip(message)
        self.style().unpolish(self)
        self.style().polish(self)


class ASLineEdit(_InputStateMixin, QLineEdit):
    """QLineEdit compatível com as duas formas comuns: ASLineEdit() e ASLineEdit('texto')."""

    def __init__(self, text: str | QWidget = "", parent: QWidget | None = None) -> None:
        if isinstance(text, QWidget):
            parent = text
            text = ""
        super().__init__(str(text), parent)
        self.setObjectName("ASInput")


class ASTextEdit(_InputStateMixin, QTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASInput")


class ASPlainTextEdit(_InputStateMixin, QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASInput")
