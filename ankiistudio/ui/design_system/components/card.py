from __future__ import annotations

from PySide6.QtWidgets import QFrame, QWidget


class ASCard(QFrame):
    VALID_VARIANTS = {"default", "raised", "interactive", "selected", "warning", "danger", "success"}

    def __init__(self, parent: QWidget | None = None, *, variant: str = "default") -> None:
        super().__init__(parent)
        self.setObjectName("ASCard")
        self.set_variant(variant)

    def set_variant(self, variant: str) -> None:
        value = variant if variant in self.VALID_VARIANTS else "default"
        self.setProperty("asVariant", value)
        self.style().unpolish(self)
        self.style().polish(self)
