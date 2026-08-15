from __future__ import annotations

from PySide6.QtWidgets import QDialog, QWidget


class ASDialog(QDialog):
    """Base de diálogos do BenkyouStudio; centraliza semântica e styling."""

    def __init__(self, parent: QWidget | None = None, *, dialog_role: str = "default") -> None:
        super().__init__(parent)
        self.setObjectName("ASDialog")
        self.setProperty("asDialogRole", dialog_role)
