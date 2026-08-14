from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool
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
from ankiistudio.ui.design_system.components import ASButton, ASComboBox, ASDialog, ASTableWidget
from ankiistudio.services.audio_import_service import (
    MATCH_FIELDS,
    SUPPORTED_AUDIO_EXTENSIONS,
    AudioImportMatch,
    AudioImportService,
    AudioImportSummary,
)
from ankiistudio.ui.workers import Worker


class AudioBatchImportDialog(ASDialog):
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
        self.thread_pool = QThreadPool.globalInstance()
        self._import_worker: Worker | None = None

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
        self.field_combo = ASComboBox()
        for key, label in MATCH_FIELDS.items():
            self.field_combo.addItem(label, key)
        self.field_combo.currentIndexChanged.connect(self.refresh_preview)
        settings.addWidget(self.field_combo, 0, 1)

        settings.addWidget(QLabel("Se já existir áudio"), 1, 0)
        self.conflict_combo = ASComboBox()
        self.conflict_combo.addItem("Ignorar", "skip")
        self.conflict_combo.addItem("Substituir", "replace")
        settings.addWidget(self.conflict_combo, 1, 1)
        settings.setColumnStretch(1, 1)
        root.addLayout(settings)

        file_actions = QHBoxLayout()
        self.select_files_button = ASButton("Selecionar arquivos")
        self.select_folder_button = ASButton("Selecionar pasta")
        self.select_files_button.setObjectName("SubtleButton")
        self.select_folder_button.setObjectName("SubtleButton")
        self.select_files_button.clicked.connect(self.select_files)
        self.select_folder_button.clicked.connect(self.select_folder)
        file_actions.addWidget(self.select_files_button)
        file_actions.addWidget(self.select_folder_button)
        file_actions.addStretch(1)
        root.addLayout(file_actions)

        self.table = ASTableWidget(0, 3)
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
        self.cancel_button = ASButton("Cancelar")
        self.import_button = ASButton("Importar correspondências")
        self.import_button.setObjectName("PrimaryButton")
        self.import_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.reject)
        self.import_button.clicked.connect(self.apply_import)
        actions.addWidget(self.cancel_button)
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
        if self._import_worker is not None:
            return
        policy = str(self.conflict_combo.currentData() or "skip")
        self._set_import_busy(True)
        self.summary_label.setText(tr("Importando correspondências..."))
        worker = Worker(
            self.service.apply,
            self.project,
            list(self.matches),
            conflict_policy=policy,
        )
        self._import_worker = worker
        worker.signals.result.connect(self._import_finished)
        worker.signals.error.connect(self._import_failed)
        worker.signals.finished.connect(self._import_worker_finished)
        self.thread_pool.start(worker)

    def _set_import_busy(self, busy: bool) -> None:
        for widget in (
            self.field_combo,
            self.conflict_combo,
            self.select_files_button,
            self.select_folder_button,
            self.cancel_button,
        ):
            widget.setEnabled(not busy)
        self.import_button.setEnabled(not busy and any(match.matched for match in self.matches))

    def _import_finished(self, result: object) -> None:
        if not isinstance(result, AudioImportSummary):
            self._import_failed("A importação retornou um resultado inválido.")
            return
        self.summary = result
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

    def _import_failed(self, message: str) -> None:
        QMessageBox.critical(self, tr("Falha na importação"), tr(message))
        self._set_import_busy(False)

    def _import_worker_finished(self) -> None:
        self._import_worker = None
        if self.isVisible() and self.summary is None:
            self._set_import_busy(False)
