from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
)

from ankiistudio.models import ImportedDeck
from ankiistudio.services.import_service import DeckImportService


class ImportDeckDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Importar conteúdo da IA")
        self.resize(820, 620)
        self.imported_deck: ImportedDeck | None = None
        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Cole aqui o JSON gerado pela IA...")
        layout.addWidget(self.editor)

        actions = QHBoxLayout()
        load_button = QPushButton("Selecionar JSON ou TXT")
        validate_button = QPushButton("Validar e importar")
        validate_button.setObjectName("PrimaryButton")
        cancel_button = QPushButton("Cancelar")
        load_button.clicked.connect(self.load_file)
        validate_button.clicked.connect(self.validate_and_accept)
        cancel_button.clicked.connect(self.reject)
        actions.addWidget(load_button)
        actions.addStretch(1)
        actions.addWidget(cancel_button)
        actions.addWidget(validate_button)
        layout.addLayout(actions)

    def load_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo",
            "",
            "JSON ou texto (*.json *.txt)",
        )
        if not filename:
            return
        self.editor.setPlainText(Path(filename).read_text(encoding="utf-8-sig"))

    def validate_and_accept(self) -> None:
        try:
            self.imported_deck = DeckImportService.from_text(self.editor.toPlainText())
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível importar", str(exc))
            return
        QMessageBox.information(
            self,
            "Conteúdo válido",
            f"Foram encontrados {len(self.imported_deck.cards)} cartões válidos.",
        )
        self.accept()
