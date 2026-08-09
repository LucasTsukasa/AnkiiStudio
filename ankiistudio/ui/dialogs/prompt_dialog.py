from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
)


class PromptDialog(QDialog):
    def __init__(self, prompt: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prompt para usar em uma IA")
        self.resize(820, 620)
        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit(prompt)
        self.editor.setReadOnly(True)
        layout.addWidget(self.editor)

        actions = QHBoxLayout()
        copy_button = QPushButton("Copiar prompt")
        copy_button.setObjectName("PrimaryButton")
        save_button = QPushButton("Salvar como TXT")
        copy_button.clicked.connect(self.copy_prompt)
        save_button.clicked.connect(self.save_prompt)
        actions.addWidget(copy_button)
        actions.addWidget(save_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def copy_prompt(self) -> None:
        QGuiApplication.clipboard().setText(self.editor.toPlainText())
        QMessageBox.information(self, "Prompt copiado", "O prompt foi copiado para a área de transferência.")

    def save_prompt(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar prompt",
            "prompt_ankiistudio.txt",
            "Arquivo de texto (*.txt)",
        )
        if filename:
            with open(filename, "w", encoding="utf-8") as stream:
                stream.write(self.editor.toPlainText())
