from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget


class ASButton(QPushButton):
    """Botão oficial do BenkyouStudio com variantes semânticas."""

    VALID_VARIANTS = {"default", "primary", "secondary", "ghost", "danger", "icon"}

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        *,
        variant: str = "default",
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName("ASButton")
        self.set_variant(variant)

    def set_variant(self, variant: str) -> None:
        value = variant if variant in self.VALID_VARIANTS else "default"
        self.setProperty("asVariant", value)
        self.style().unpolish(self)
        self.style().polish(self)

    @property
    def variant(self) -> str:
        return str(self.property("asVariant") or "default")
