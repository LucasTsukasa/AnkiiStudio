from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from ankiistudio.i18n import tr
from ankiistudio.models import FlashcardData, ProjectData
from ankiistudio.services.audio_import_service import (
    MATCH_FIELDS,
    SUPPORTED_AUDIO_EXTENSIONS,
    AudioImportMatch,
    AudioImportService,
    AudioImportSummary,
)


class AudioBatchImportDialog(QDialog):
    def __init__(
        self,
        project: ProjectData,
        cards: list[FlashcardData],
        service: AudioImportService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.cards = cards
        self.service = service
        self.files: list[Path] = []
        self.matches: list[AudioImportMatch] = []
        self.summary: AudioImportSummary | None = None

        self.setWindowTitle("Importar áudios em lote")
        self.resize(880, 620)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Associe arquivos aos cartões pelo nome do arquivo. Por exemplo, "
            "‘あ.wav’ corresponde ao valor ‘あ’ no campo selecionado."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        settings = QGridLayout()
        settings.setHorizontalSpacing(10)
        settings.setVerticalSpacing(8)

        settings.addWidget(QLabel("Correspondência"), 0, 0)
        self.field_combo = QComboBox()
        for key, label in MATCH_FIELDS.items():
            self.field_combo.addItem(label, key)
        self.field_combo.currentIndexChanged.connect(self.refresh_preview)
        settings.addWidget(self.field_combo, 0, 1)

        settings.addWidget(QLabel("Se já existir áudio"), 1, 0)
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem("Ignorar", "skip")
        self.conflict_combo.addItem("Substituir", "replace")
        settings.addWidget(self.conflict_combo, 1, 1)
        settings.setColumnStretch(1, 1)
        root.addLayout(settings)

        file_actions = QHBoxLayout()
        select_files = QPushButton("Selecionar arquivos")
        select_folder = QPushButton("Selecionar pasta")
        select_files.setObjectName("SubtleButton")
        select_folder.setObjectName("SubtleButton")
        select_files.clicked.connect(self.select_files)
        select_folder.clicked.connect(self.select_folder)
        file_actions.addWidget(select_files)
        file_actions.addWidget(select_folder)
        file_actions.addStretch(1)
        root.addLayout(file_actions)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Arquivo", "Cartão", "Status"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        self.summary_label = QLabel("Selecione arquivos ou uma pasta para visualizar as correspondências.")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_button = QPushButton("Cancelar")
        self.import_button = QPushButton("Importar correspondências")
        self.import_button.setObjectName("PrimaryButton")
        self.import_button.setEnabled(False)
        cancel_button.clicked.connect(self.reject)
        self.import_button.clicked.connect(self.apply_import)
        actions.addWidget(cancel_button)
        actions.addWidget(self.import_button)
        root.addLayout(actions)

    @staticmethod
    def _file_filter() -> str:
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_AUDIO_EXTENSIONS))
        return f"Arquivos de áudio ({patterns});;Todos os arquivos (*)"

    def select_files(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar áudios",
            "",
            self._file_filter(),
        )
        if not filenames:
            return
        self.files = [Path(filename) for filename in filenames]
        self.refresh_preview()

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta de áudios")
        if not folder:
            return
        self.files = self.service.supported_files_in_folder(Path(folder))
        if not self.files:
            QMessageBox.information(
                self,
                "Nenhum áudio encontrado",
                "A pasta selecionada não contém arquivos de áudio compatíveis.",
            )
        self.refresh_preview()

    def refresh_preview(self, _index: int | None = None) -> None:
        field = str(self.field_combo.currentData() or "word")
        self.matches = self.service.preview(self.project, self.cards, self.files, field)
        self.table.setRowCount(len(self.matches))

        counts = {"matched": 0, "unmatched": 0, "ambiguous": 0, "unsupported": 0, "existing": 0}
        labels = {
            "matched": tr("Correspondência"),
            "unmatched": tr("Não encontrado"),
            "ambiguous": tr("Ambíguo"),
            "unsupported": tr("Formato não suportado"),
        }
        for row, match in enumerate(self.matches):
            if match.matched and match.existing_audio:
                counts["existing"] += 1
                status = tr("Já possui áudio")
            else:
                status = labels.get(match.status, match.status)
            counts[match.status] = counts.get(match.status, 0) + 1
            self.table.setItem(row, 0, QTableWidgetItem(match.source_name))
            self.table.setItem(row, 1, QTableWidgetItem(match.card_word or "—"))
            self.table.setItem(row, 2, QTableWidgetItem(status))

        self.summary_label.setText(tr(
            f"Arquivos: {len(self.matches)} · Correspondências: {counts['matched']} · "
            f"Sem cartão: {counts['unmatched']} · Ambíguos: {counts['ambiguous']} · "
            f"Já com áudio: {counts['existing']}"
        ))
        self.import_button.setEnabled(any(match.matched for match in self.matches))

    def apply_import(self) -> None:
        policy = str(self.conflict_combo.currentData() or "skip")
        self.summary = self.service.apply(self.project, self.matches, conflict_policy=policy)
        message = (
            f"Importados: {self.summary.imported}\n"
            f"Ignorados por já possuir áudio: {self.summary.skipped_existing}\n"
            f"Sem correspondência: {self.summary.unmatched}\n"
            f"Ambíguos: {self.summary.ambiguous}\n"
            f"Formatos não suportados: {self.summary.unsupported}\n"
            f"Falhas: {self.summary.errors}"
        )
        QMessageBox.information(self, tr("Importação concluída"), tr(message))
        self.accept()
