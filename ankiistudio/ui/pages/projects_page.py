from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import AppPaths
from ankiistudio.database import Database
from ankiistudio.i18n import tr
from ankiistudio.models import FlashcardData, ProjectData
from ankiistudio.services.anki_export_service import AnkiExportService
from ankiistudio.services.audio_service import ProjectAudioService
from ankiistudio.services.audio_import_service import AudioImportService, SUPPORTED_AUDIO_EXTENSIONS
from ankiistudio.services.image_service import ImageService
from ankiistudio.services.image_sources import ImageSearchService
from ankiistudio.services.media_service import CardImageService, SUPPORTED_IMAGE_EXTENSIONS
from ankiistudio.services.project_service import ProjectService
from ankiistudio.ui.dialogs.image_search_dialog import ImageSearchDialog
from ankiistudio.ui.dialogs.audio_batch_import_dialog import AudioBatchImportDialog
from ankiistudio.ui.widgets import AdaptiveSplitter, PageHeader, PageScrollArea, SectionCard, StatusBanner
from ankiistudio.ui.workers import Worker


class ProjectsPage(QWidget):
    changed = Signal()

    def __init__(self, database: Database, paths: AppPaths) -> None:
        super().__init__()
        self.database = database
        self.paths = paths
        self.thread_pool = QThreadPool.globalInstance()
        self.current_project: ProjectData | None = None
        self.current_card: FlashcardData | None = None
        self._pending_cards: dict[int, FlashcardData] = {}
        self._loading_form = False
        self.image_search_service = ImageSearchService(database)
        self.image_service = CardImageService(database, self.image_search_service, ImageService(paths.images_dir))
        self.audio_service = ProjectAudioService(database, paths)
        self.audio_import_service = AudioImportService(self.audio_service)
        self.export_service = AnkiExportService()
        self._workers: list[Worker] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(22, 20, 22, 22)
        root.setSpacing(12)
        root.addWidget(PageHeader(
            "Projetos",
            "Revise os cartões, processe mídias e selecione o conteúdo que será exportado.",
        ))
        self.status = StatusBanner()
        root.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        root.addWidget(self.progress)

        toolbar = SectionCard()
        toolbar_row = QGridLayout()
        toolbar_row.setHorizontalSpacing(10)
        toolbar_row.setVerticalSpacing(8)
        project_label = QLabel("Projeto")
        project_label.setObjectName("FieldLabel")
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self.load_project)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.setObjectName("SubtleButton")
        self.delete_project_button = QPushButton("Excluir projeto")
        self.delete_project_button.setObjectName("DangerButton")
        self.export_selected_button = QPushButton("Exportar selecionados")
        self.export_selected_button.setObjectName("SubtleButton")
        self.export_all_button = QPushButton("Exportar todos")
        self.export_all_button.setObjectName("PrimaryButton")
        self.export_button = self.export_all_button
        self.refresh_button.clicked.connect(self.refresh)
        self.delete_project_button.clicked.connect(self.delete_project)
        self.export_selected_button.clicked.connect(self.export_selected)
        self.export_button.clicked.connect(self.export_project)
        toolbar_row.addWidget(project_label, 0, 0)
        toolbar_row.addWidget(self.project_combo, 0, 1, 1, 5)
        toolbar_row.addWidget(self.refresh_button, 1, 0)
        toolbar_row.addWidget(self.delete_project_button, 1, 1)
        toolbar_row.setColumnStretch(2, 1)
        toolbar_row.addWidget(self.export_selected_button, 1, 4)
        toolbar_row.addWidget(self.export_all_button, 1, 5)
        toolbar.root.addLayout(toolbar_row)
        root.addWidget(toolbar)

        splitter = AdaptiveSplitter(breakpoint=900)

        left_card = SectionCard(
            "Cartões",
            "Marque os cartões que deseja exportar. Selecione uma linha para editar o conteúdo.",
        )
        left_card.setMinimumHeight(430)
        self.table = QTableWidget(0, 6)
        self.table.setMinimumHeight(330)
        self.table.setHorizontalHeaderLabels(["Exportar", "Grupo", "Palavra", "Tradução", "Imagem", "Áudio"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.load_selected_card)
        left_card.root.addWidget(self.table, 1)

        selection_actions = QGridLayout()
        selection_actions.setHorizontalSpacing(8)
        selection_actions.setVerticalSpacing(8)
        self.select_all_button = QPushButton("Marcar todos")
        self.select_none_button = QPushButton("Desmarcar todos")
        self.add_card_button = QPushButton("Adicionar cartão")
        self.delete_card_button = QPushButton("Excluir cartão")
        for button in (self.select_all_button, self.select_none_button, self.add_card_button):
            button.setObjectName("SubtleButton")
        self.delete_card_button.setObjectName("DangerButton")
        self.select_all_button.clicked.connect(lambda: self._set_export_checks(True))
        self.select_none_button.clicked.connect(lambda: self._set_export_checks(False))
        self.add_card_button.clicked.connect(self.add_card)
        self.delete_card_button.clicked.connect(self.delete_card)
        selection_actions.addWidget(self.select_all_button, 0, 0)
        selection_actions.addWidget(self.select_none_button, 0, 1)
        selection_actions.addWidget(self.add_card_button, 1, 0)
        selection_actions.addWidget(self.delete_card_button, 1, 1)
        left_card.root.addLayout(selection_actions)
        splitter.addWidget(left_card)

        editor_content = QWidget()
        editor_content_layout = QVBoxLayout(editor_content)
        editor_content_layout.setContentsMargins(0, 0, 0, 0)
        editor_content_layout.setSpacing(10)
        editor_card = SectionCard(
            "Editar cartão",
            "Somente os campos utilizados pela estrutura atual são exibidos, além dos dados necessários às mídias.",
        )
        self.form = QFormLayout()
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(7)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.section_combo = QComboBox()
        self.word = QLineEdit()
        self.reading = QLineEdit()
        self.romanization = QLineEdit()
        self.translation = QLineEdit()
        self.example = QLineEdit()
        self.explanation = QTextEdit()
        self.explanation.setMaximumHeight(100)
        self.mnemonic = QTextEdit()
        self.mnemonic.setMaximumHeight(84)
        self._field_labels: dict[QWidget, QLabel] = {}
        for label, widget in (
            ("Subbaralho", self.section_combo),
            ("Conteúdo principal", self.word),
            ("Leitura", self.reading),
            ("Romaji / Romanização", self.romanization),
            ("Tradução", self.translation),
            ("Exemplo", self.example),
            ("Explicação", self.explanation),
            ("Mnemônico", self.mnemonic),
        ):
            label_widget = QLabel(label)
            self._field_labels[widget] = label_widget
            self.form.addRow(label_widget, widget)
        self.section_combo.currentIndexChanged.connect(self._editor_changed)
        for line_edit in (self.word, self.reading, self.romanization, self.translation, self.example):
            line_edit.textEdited.connect(self._editor_changed)
        self.explanation.textChanged.connect(self._editor_changed)
        self.mnemonic.textChanged.connect(self._editor_changed)
        editor_card.root.addLayout(self.form)
        editor_content_layout.addWidget(editor_card)

        media_card = SectionCard(
            "Mídias",
            "Gere mídias automaticamente ou associe arquivos de áudio próprios aos cartões.",
        )
        media_row = QGridLayout()
        media_row.setHorizontalSpacing(8)
        media_row.setVerticalSpacing(8)
        self.image_button = QPushButton("Pesquisar imagem")
        self.bulk_image_button = QPushButton("Imagens para todos")
        self.import_image_button = QPushButton("Importar imagem")
        self.remove_image_button = QPushButton("Remover imagem")
        self.audio_button = QPushButton("Áudio deste cartão")
        self.bulk_audio_button = QPushButton("Áudios para todos")
        self.import_audio_button = QPushButton("Importar áudio")
        self.batch_import_audio_button = QPushButton("Importar áudios em lote")
        self.remove_audio_button = QPushButton("Remover áudio")
        self.save_button = QPushButton("Salvar alterações")
        for button in (
            self.image_button,
            self.bulk_image_button,
            self.import_image_button,
            self.audio_button,
            self.bulk_audio_button,
            self.import_audio_button,
            self.batch_import_audio_button,
        ):
            button.setObjectName("SubtleButton")
        self.remove_image_button.setObjectName("DangerButton")
        self.remove_audio_button.setObjectName("DangerButton")
        self.save_button.setObjectName("PrimaryButton")
        self.image_button.clicked.connect(self.search_image)
        self.bulk_image_button.clicked.connect(self.generate_all_images)
        self.import_image_button.clicked.connect(self.import_card_image)
        self.remove_image_button.clicked.connect(self.remove_card_image)
        self.audio_button.clicked.connect(self.generate_card_audio)
        self.bulk_audio_button.clicked.connect(self.generate_all_audio)
        self.import_audio_button.clicked.connect(self.import_card_audio)
        self.batch_import_audio_button.clicked.connect(self.import_audio_batch)
        self.remove_audio_button.clicked.connect(self.remove_card_audio)
        self.save_button.clicked.connect(self.save_card)
        media_row.addWidget(self.image_button, 0, 0)
        media_row.addWidget(self.bulk_image_button, 0, 1)
        media_row.addWidget(self.import_image_button, 1, 0)
        media_row.addWidget(self.remove_image_button, 1, 1)
        media_row.addWidget(self.audio_button, 2, 0)
        media_row.addWidget(self.bulk_audio_button, 2, 1)
        media_row.addWidget(self.import_audio_button, 3, 0)
        media_row.addWidget(self.batch_import_audio_button, 3, 1)
        media_row.addWidget(self.remove_audio_button, 4, 0, 1, 2)
        media_row.addWidget(self.save_button, 5, 0, 1, 2)
        media_card.root.addLayout(media_row)
        editor_content_layout.addWidget(media_card)
        editor_content_layout.addStretch(1)

        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor_scroll.setMinimumHeight(430)
        editor_scroll.setWidget(editor_content)
        splitter.addWidget(editor_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([650, 430])
        root.addWidget(splitter, 1)
        root.addStretch(0)

        outer.addWidget(PageScrollArea(content))
        self.refresh()

    def _keep_worker(self, worker: Worker) -> None:
        self._workers.append(worker)
        worker.signals.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        self.thread_pool.start(worker)

    def _set_field_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label = self._field_labels.get(widget)
        if label is not None:
            label.setVisible(visible)

    def _apply_structure_visibility(self) -> None:
        project = self.current_project
        if project is None:
            return
        if self.current_card is not None:
            variation = project.structure_for_card(self.current_card)
            selected = set(variation.front_components + variation.back_components)
        else:
            selected = set(project.required_components())
        self._set_field_visible(self.section_combo, True)
        self._set_field_visible(self.word, True)
        self._set_field_visible(self.reading, "reading" in selected)
        self._set_field_visible(self.romanization, "romanization" in selected)
        self._set_field_visible(self.translation, "translation" in selected)
        self._set_field_visible(self.example, "example" in selected)
        self._set_field_visible(self.explanation, "explanation" in selected)
        self._set_field_visible(self.mnemonic, "mnemonic" in selected)

    def _selected_card_ids(self) -> list[int]:
        ids: list[int] = []
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return ids
        for index in selection_model.selectedRows():
            item = self.table.item(index.row(), 0)
            if item is None:
                continue
            card_id = item.data(Qt.ItemDataRole.UserRole)
            if card_id is not None and int(card_id) not in ids:
                ids.append(int(card_id))
        return ids

    def _update_action_states(self) -> None:
        has_project = self.current_project is not None and self.current_project.id is not None
        has_card = self.current_card is not None and self.current_card.id is not None
        selected_ids = self._selected_card_ids()
        for button in (
            self.export_selected_button,
            self.export_all_button,
            self.delete_project_button,
            self.add_card_button,
            self.select_all_button,
            self.select_none_button,
        ):
            button.setEnabled(has_project)
        self.delete_card_button.setEnabled(bool(selected_ids))
        self.delete_card_button.setText(
            tr(f"Excluir {len(selected_ids)} cartões") if len(selected_ids) > 1 else tr("Excluir cartão")
        )
        self.save_button.setEnabled(bool(self._pending_cards))
        self.save_button.setText(
            tr(f"Salvar alterações ({len(self._pending_cards)})")
            if self._pending_cards
            else tr("Salvar alterações")
        )

        project_uses_images = bool(has_project and self.current_project and self.current_project.uses_images)
        project_uses_audio = bool(has_project and self.current_project and self.current_project.uses_audio)
        card_uses_images = bool(
            has_card and self.current_project and self.current_card
            and self.current_project.card_uses_component(self.current_card, "image")
        )
        card_uses_audio = bool(
            has_card and self.current_project and self.current_card
            and self.current_project.card_uses_component(self.current_card, "audio")
        )
        has_image = bool(has_card and self.current_card and self.current_card.image_path)
        has_audio = bool(has_card and self.current_card and self.current_card.audio_path)
        self.image_button.setEnabled(card_uses_images)
        self.import_image_button.setEnabled(card_uses_images)
        self.remove_image_button.setEnabled(card_uses_images and has_image)
        self.bulk_image_button.setEnabled(has_project and project_uses_images)
        self.audio_button.setEnabled(card_uses_audio)
        self.bulk_audio_button.setEnabled(has_project and project_uses_audio)
        self.import_audio_button.setEnabled(card_uses_audio)
        self.remove_audio_button.setEnabled(card_uses_audio and has_audio)
        self.batch_import_audio_button.setEnabled(has_project and project_uses_audio)
        self.image_button.setToolTip("" if card_uses_images else "A variação deste cartão não utiliza Imagem.")
        self.import_image_button.setToolTip("" if card_uses_images else "A variação deste cartão não utiliza Imagem.")
        self.remove_image_button.setToolTip("" if has_image else "Este cartão não possui imagem associada.")
        self.bulk_image_button.setToolTip("" if project_uses_images else "Este projeto não utiliza Imagem.")
        self.audio_button.setToolTip("" if card_uses_audio else "A variação deste cartão não utiliza Áudio.")
        self.import_audio_button.setToolTip("" if card_uses_audio else "A variação deste cartão não utiliza Áudio.")
        self.remove_audio_button.setToolTip("" if has_audio else "Este cartão não possui áudio associado.")
        self.bulk_audio_button.setToolTip("" if project_uses_audio else "Este projeto não utiliza Áudio.")
        self.batch_import_audio_button.setToolTip("" if project_uses_audio else "Este projeto não utiliza Áudio.")

    def refresh(self, select_project_id: int | None = None) -> None:
        current = select_project_id
        if current is None and self.current_project is not None:
            current = self.current_project.id
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        projects = self.database.list_projects()
        for project in projects:
            self.project_combo.addItem(project.name, project.id)
        if not projects:
            self.project_combo.blockSignals(False)
            self.current_project = None
            self.current_card = None
            self._pending_cards.clear()
            self.table.setRowCount(0)
            self.clear_form()
            self._update_action_states()
            return
        index = 0
        if current is not None:
            for candidate in range(self.project_combo.count()):
                if self.project_combo.itemData(candidate) == current:
                    index = candidate
                    break
        self.project_combo.setCurrentIndex(index)
        self.project_combo.blockSignals(False)
        self.load_project()

    def load_project(self) -> None:
        project_id = self.project_combo.currentData()
        if project_id is None:
            return
        project_id = int(project_id)
        previous_id = self.current_project.id if self.current_project is not None else None
        if previous_id is not None and previous_id != project_id and self._pending_cards:
            if not self.resolve_pending_changes("trocar de projeto"):
                old_index = self.project_combo.findData(previous_id)
                if old_index >= 0:
                    self.project_combo.blockSignals(True)
                    self.project_combo.setCurrentIndex(old_index)
                    self.project_combo.blockSignals(False)
                return
        self.current_project = self.database.get_project(project_id)
        self.current_card = None
        self._populate_section_combo()
        self._apply_structure_visibility()
        self.populate_cards()
        self._update_action_states()

    def _populate_section_combo(self, current: str = "") -> None:
        self.section_combo.blockSignals(True)
        self.section_combo.clear()
        self.section_combo.addItem("Baralho principal", "")
        if self.current_project:
            for section in self.current_project.deck_sections:
                self.section_combo.addItem(section, section)
        if current and self.section_combo.findData(current) < 0:
            self.section_combo.addItem(current, current)
        index = self.section_combo.findData(current)
        self.section_combo.setCurrentIndex(index if index >= 0 else 0)
        self.section_combo.blockSignals(False)

    def populate_cards(self, select_card_id: int | None = None) -> None:
        checked_ids = set(self.checked_card_ids())
        had_rows = self.table.rowCount() > 0
        if select_card_id is None and self.current_card is not None:
            select_card_id = self.current_card.id
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.current_card = None
        self.clear_form()
        if self.current_project is None or self.current_project.id is None:
            self.table.blockSignals(False)
            self._update_action_states()
            return
        cards = self.database.list_cards(self.current_project.id)
        display_cards = [self._pending_cards.get(int(card.id or 0), card) for card in cards]
        self.table.setRowCount(len(display_cards))
        for row, card in enumerate(display_cards):
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check_item.setCheckState(
                Qt.CheckState.Checked if (not had_rows or card.id in checked_ids) else Qt.CheckState.Unchecked
            )
            check_item.setData(Qt.ItemDataRole.UserRole, card.id)
            self.table.setItem(row, 0, check_item)

            needs_image = self.current_project.card_uses_component(card, "image")
            needs_audio = self.current_project.card_uses_component(card, "audio")
            image_ok = self.image_service.has_valid_image(card) if needs_image else False
            audio_ok, _ = self.audio_service.audio_status(self.current_project, card)
            values = [
                card.section or "Principal",
                card.word,
                card.translation,
                ("Sim" if image_ok else "Não") if needs_image else "—",
                ("Sim" if audio_ok else "Não") if needs_audio else "—",
            ]
            for column, value in enumerate(values, start=1):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.blockSignals(False)
        target_row = -1
        if select_card_id is not None:
            target_row = self._row_for_card_id(select_card_id)
        if target_row < 0 and display_cards:
            target_row = 0
        if target_row >= 0:
            self.table.selectRow(target_row)
        else:
            self._update_action_states()

    def checked_card_ids(self) -> list[int]:
        ids: list[int] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                card_id = item.data(Qt.ItemDataRole.UserRole)
                if card_id is not None:
                    ids.append(int(card_id))
        return ids

    def _set_export_checks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(state)

    def load_selected_card(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.current_card = None
            self.clear_form()
            self._update_action_states()
            return
        row = self.table.currentRow()
        selected_row_numbers = {index.row() for index in rows}
        if row not in selected_row_numbers:
            row = rows[0].row()
        item = self.table.item(row, 0)
        if item is None:
            return
        card_id = int(item.data(Qt.ItemDataRole.UserRole))
        self.current_card = self._pending_cards.get(card_id) or self.database.get_card(card_id)
        if self.current_card:
            self.fill_form(self.current_card)
        self._update_action_states()

    def fill_form(self, card: FlashcardData) -> None:
        self._loading_form = True
        try:
            self._populate_section_combo(card.section)
            self.word.setText(card.word)
            self.reading.setText(card.reading)
            self.romanization.setText(card.romanization)
            self.translation.setText(card.translation)
            self.example.setText(card.example)
            self.explanation.setPlainText(card.explanation)
            self.mnemonic.setPlainText(card.mnemonic)
            self._apply_structure_visibility()
        finally:
            self._loading_form = False

    def clear_form(self) -> None:
        self._loading_form = True
        try:
            self._populate_section_combo("")
            for widget in (
                self.word,
                self.reading,
                self.romanization,
                self.translation,
                self.example,
            ):
                widget.clear()
            self.explanation.clear()
            self.mnemonic.clear()
        finally:
            self._loading_form = False

    def collect_card(self) -> FlashcardData:
        if self.current_card is None:
            raise ValueError("Selecione um cartão.")
        return self.current_card.model_copy(
            update={
                "section": str(self.section_combo.currentData() or ""),
                "word": self.word.text().strip(),
                "reading": self.reading.text().strip(),
                "romanization": self.romanization.text().strip(),
                "translation": self.translation.text().strip(),
                "example": self.example.text().strip(),
                "explanation": self.explanation.toPlainText().strip(),
                "mnemonic": self.mnemonic.toPlainText().strip(),
            }
        )

    def _editor_changed(self, *_args) -> None:
        if self._loading_form or self.current_card is None or self.current_card.id is None:
            return
        draft = self.collect_card()
        card_id = int(draft.id)
        self._pending_cards[card_id] = draft
        self.current_card = draft
        row = self._row_for_card_id(card_id)
        if row >= 0:
            for column, value in ((1, draft.section or "Principal"), (2, draft.word), (3, draft.translation)):
                item = self.table.item(row, column)
                if item is not None:
                    item.setText(value)
        self.status.show_message("Há alterações não salvas.")
        self._update_action_states()

    def save_pending_changes(self) -> bool:
        if self.current_card is not None and self.current_card.id is not None and not self._loading_form:
            # textEdited/textChanged já mantêm o rascunho atualizado; esta captura cobre alterações via teclado/combobox.
            if int(self.current_card.id) in self._pending_cards:
                self._pending_cards[int(self.current_card.id)] = self.collect_card()
        if not self._pending_cards:
            return True
        drafts = list(self._pending_cards.values())
        invalid = [card.word or f"Cartão #{card.id}" for card in drafts if not card.word.strip()]
        if invalid:
            QMessageBox.warning(
                self,
                "Conteúdo principal obrigatório",
                "Preencha o conteúdo principal antes de salvar todas as alterações.",
            )
            return False
        selected_id = self.current_card.id if self.current_card is not None else None
        try:
            self.database.update_cards(drafts)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar", str(exc))
            return False
        count = len(drafts)
        self._pending_cards.clear()
        self.status.show_message(f"{count} cartão(ões) salvo(s).")
        self.populate_cards(select_card_id=selected_id)
        self.changed.emit()
        return True

    def save_card(self) -> None:
        self.save_pending_changes()

    def discard_pending_changes(self) -> None:
        selected_id = self.current_card.id if self.current_card is not None else None
        self._pending_cards.clear()
        if self.current_project is not None:
            self.populate_cards(select_card_id=selected_id)

    def resolve_pending_changes(self, action: str) -> bool:
        if not self._pending_cards:
            return True
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("Alterações não salvas")
        message.setText(tr(f"Existem alterações não salvas antes de {action}."))
        message.setInformativeText("Deseja salvar as alterações antes de continuar?")
        message.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        save_button = message.button(QMessageBox.StandardButton.Save)
        discard_button = message.button(QMessageBox.StandardButton.Discard)
        cancel_button = message.button(QMessageBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText(tr("Salvar alterações"))
        if discard_button is not None:
            discard_button.setText(tr("Continuar sem salvar"))
        if cancel_button is not None:
            cancel_button.setText(tr("Cancelar"))
        result = message.exec()
        if result == QMessageBox.StandardButton.Save:
            return self.save_pending_changes()
        if result == QMessageBox.StandardButton.Discard:
            self.discard_pending_changes()
            return True
        return False

    def confirm_close(self) -> bool:
        return self.resolve_pending_changes("sair do aplicativo")

    def add_card(self) -> None:
        if self.current_project is None or self.current_project.id is None:
            QMessageBox.warning(self, "Sem projeto", "Selecione um projeto.")
            return
        existing_cards = self.database.list_cards(self.current_project.id)
        structure_key = ProjectService.next_structure_key(self.current_project, existing_cards)
        ids = self.database.add_cards(
            self.current_project.id,
            [FlashcardData(word="Novo cartão", structure_key=structure_key)],
        )
        self.populate_cards(select_card_id=ids[0])
        self.changed.emit()

    def delete_card(self) -> None:
        card_ids = self._selected_card_ids()
        if not card_ids:
            QMessageBox.warning(self, "Sem cartão", "Selecione ao menos um cartão para excluir.")
            return
        if len(card_ids) == 1:
            card = self._pending_cards.get(card_ids[0]) or self.database.get_card(card_ids[0])
            label = card.word if card is not None else f"#{card_ids[0]}"
            question = f"Excluir o cartão “{label}”?"
            title = "Excluir cartão"
        else:
            question = f"Excluir os {len(card_ids)} cartões selecionados?"
            title = "Excluir cartões"
        if QMessageBox.question(self, title, question) != QMessageBox.StandardButton.Yes:
            return
        self.database.delete_cards(card_ids)
        for card_id in card_ids:
            self._pending_cards.pop(card_id, None)
        self.current_card = None
        self.populate_cards()
        self.status.show_message(f"{len(card_ids)} cartão(ões) excluído(s).")
        self.changed.emit()

    def delete_project(self) -> None:
        if self.current_project is None or self.current_project.id is None:
            QMessageBox.warning(self, "Sem projeto", "Selecione um projeto para excluir.")
            return
        if self._pending_cards and not self.resolve_pending_changes("excluir o projeto"):
            return
        if QMessageBox.question(
            self,
            "Excluir projeto",
            f"Excluir o projeto “{self.current_project.name}” e todos os seus cartões?",
        ) != QMessageBox.StandardButton.Yes:
            return
        project_id = self.current_project.id
        self.database.delete_project(project_id)
        self._pending_cards.clear()
        self.current_card = None
        self.current_project = None
        self.refresh()
        self.changed.emit()

    def _persisted_current_card(self) -> FlashcardData | None:
        if self.current_card is None or self.current_card.id is None:
            return None
        return self.database.get_card(int(self.current_card.id))

    def _merge_media_into_draft(self, updated: FlashcardData) -> FlashcardData:
        if updated.id is None:
            return updated
        card_id = int(updated.id)
        draft = self._pending_cards.get(card_id)
        if draft is not None:
            draft = draft.model_copy(
                update={
                    "image_path": updated.image_path,
                    "word_audio_path": updated.word_audio_path,
                    "sentence_audio_path": updated.sentence_audio_path,
                }
            )
            self._pending_cards[card_id] = draft
            return draft
        return updated

    def search_image(self) -> None:
        if self.current_project is None or self.current_card is None:
            QMessageBox.warning(self, "Seleção necessária", "Selecione um cartão.")
            return
        if not self.current_project.card_uses_component(self.current_card, "image"):
            return
        term, auxiliary_terms = CardImageService.manual_search_terms(self.current_card)
        dialog = ImageSearchDialog(
            term,
            self.image_search_service,
            self,
            auxiliary_terms=auxiliary_terms,
        )
        if not dialog.exec() or dialog.selected_result is None:
            return
        persisted = self._persisted_current_card()
        if persisted is None:
            return
        self.status.show_message("Baixando e otimizando a imagem...")
        worker = Worker(
            self.image_service.apply_search_result,
            self.current_project,
            persisted,
            dialog.selected_result,
        )
        worker.signals.result.connect(self._image_applied)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        self._keep_worker(worker)

    def import_card_image(self) -> None:
        project = self.current_project
        if project is None or self.current_card is None:
            return
        if not project.card_uses_component(self.current_card, "image"):
            return
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_IMAGE_EXTENSIONS))
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Importar imagem para o cartão",
            "",
            f"Arquivos de imagem ({patterns});;Todos os arquivos (*)",
        )
        if not filename:
            return
        persisted = self._persisted_current_card()
        if persisted is None:
            return
        try:
            updated = self.image_service.import_image_file(project, persisted, Path(filename))
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível importar", str(exc))
            return
        self._image_applied(updated, message="Imagem importada e associada ao cartão.")

    def remove_card_image(self) -> None:
        if self.current_card is None or not self.current_card.image_path:
            return
        if QMessageBox.question(
            self,
            "Remover imagem",
            "Remover a imagem associada a este cartão?",
        ) != QMessageBox.StandardButton.Yes:
            return
        persisted = self._persisted_current_card()
        if persisted is None:
            return
        try:
            updated = self.image_service.remove_image(persisted)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível remover", str(exc))
            return
        self._image_applied(updated, message="Imagem removida do cartão.")

    def _image_applied(self, card: object, message: str = "Imagem associada e validada.") -> None:
        if not isinstance(card, FlashcardData):
            return
        self.current_card = self._merge_media_into_draft(card)
        card_id = self.current_card.id
        self.status.show_message(message)
        self.populate_cards(select_card_id=card_id)
        self.changed.emit()

    def _row_for_card_id(self, card_id: int | None) -> int:
        if card_id is None:
            return -1
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == card_id:
                return row
        return -1

    def _set_media_status(self, card_id: int | None, column: int, text: str) -> None:
        row = self._row_for_card_id(card_id)
        if row < 0:
            return
        item = self.table.item(row, column)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(row, column, item)
        item.setText(text)

    @staticmethod
    def _progress_state_label(state: str) -> str:
        return {
            "working": "processando",
            "done": "concluído",
            "existing": "já existente",
            "error": "falhou",
        }.get(state, state)

    def _bulk_media_progress(self, percent: int, payload: str) -> None:
        self.progress.setValue(percent)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return
        kind = str(data.get("kind") or "")
        state = str(data.get("state") or "")
        card_id = data.get("card_id")
        if kind == "image":
            display = {"working": "Buscando…", "done": "Sim", "existing": "Sim", "error": "Falhou"}.get(state, state)
            self._set_media_status(card_id, 4, display)
            noun = "Imagens"
        else:
            display = {"working": "Gerando…", "done": "Sim", "existing": "Sim", "error": "Falhou"}.get(state, state)
            self._set_media_status(card_id, 5, display)
            noun = "Áudios"
        self.status.show_message(
            f"{noun}: {data.get('index')}/{data.get('total')} · {data.get('word')} · {self._progress_state_label(state)}",
            error=state == "error",
        )

    def generate_all_images(self) -> None:
        project = self.current_project
        if project is None or project.id is None or not project.uses_images:
            return
        if self._pending_cards and not self.resolve_pending_changes("buscar imagens em lote"):
            return
        cards = [
            card for card in self.database.list_cards(project.id)
            if project.card_uses_component(card, "image")
        ]
        if not cards:
            return
        if QMessageBox.question(
            self,
            "Buscar imagens",
            f"Buscar automaticamente imagens ausentes para {len(cards)} cartões usando as fontes habilitadas nas Configurações?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.bulk_image_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.status.show_message("Preparando busca de imagens...")

        def run_all() -> tuple[int, int, list[str]]:
            completed = 0
            existing = 0
            errors: list[str] = []
            total = len(cards)
            for index, card in enumerate(cards, start=1):
                worker.signals.progress.emit(
                    int((index - 1) * 100 / total),
                    json.dumps({"kind": "image", "state": "working", "card_id": card.id, "word": card.word, "index": index, "total": total}, ensure_ascii=False),
                )
                if self.image_service.has_valid_image(card):
                    existing += 1
                    state = "existing"
                else:
                    try:
                        self.image_service.apply_best_image(project, card)
                        completed += 1
                        state = "done"
                    except Exception as exc:
                        errors.append(f"{card.word}: {exc}")
                        state = "error"
                worker.signals.progress.emit(
                    int(index * 100 / total),
                    json.dumps({"kind": "image", "state": state, "card_id": card.id, "word": card.word, "index": index, "total": total}, ensure_ascii=False),
                )
            return completed, existing, errors

        worker = Worker(run_all)
        worker.signals.progress.connect(self._bulk_media_progress)
        worker.signals.result.connect(self._bulk_images_finished)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self._update_action_states())
        self._keep_worker(worker)

    def _bulk_images_finished(self, result: object) -> None:
        completed, existing, errors = result
        self.progress.setValue(100)
        if errors:
            self.status.show_message(
                f"Busca concluída: {completed} imagens adicionadas, {existing} já existiam e {len(errors)} falharam. Primeira falha: {errors[0]}",
                error=True,
            )
        else:
            self.status.show_message(f"Busca concluída: {completed} imagens adicionadas e {existing} já existentes.")
        self.populate_cards()
        self.changed.emit()

    def generate_card_audio(self) -> None:
        if (
            self.current_project is None
            or self.current_card is None
            or not self.current_project.card_uses_component(self.current_card, "audio")
        ):
            return
        if self._pending_cards and not self.resolve_pending_changes("gerar áudio"):
            return
        persisted = self._persisted_current_card()
        if persisted is None:
            return
        self.status.show_message("Gerando apenas os áudios usados pela estrutura deste cartão...")
        worker = Worker(self.audio_service.generate_for_card, self.current_project, persisted)
        worker.signals.result.connect(self._audio_generated)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        self._keep_worker(worker)

    def import_card_audio(self) -> None:
        project = self.current_project
        card = self.current_card
        if (
            project is None
            or card is None
            or not project.card_uses_component(card, "audio")
        ):
            return
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_AUDIO_EXTENSIONS))
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Importar áudio para o cartão",
            "",
            f"Arquivos de áudio ({patterns});;Todos os arquivos (*)",
        )
        if not filename:
            return
        persisted = self._persisted_current_card()
        if persisted is None:
            return
        try:
            updated = self.audio_service.import_audio_file(project, persisted, Path(filename))
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível importar", str(exc))
            return
        self._audio_generated(updated, success_message="Áudio importado e associado ao cartão.")

    def remove_card_audio(self) -> None:
        if self.current_card is None or not self.current_card.audio_path:
            return
        if QMessageBox.question(
            self,
            "Remover áudio",
            "Remover o áudio associado a este cartão?",
        ) != QMessageBox.StandardButton.Yes:
            return
        persisted = self._persisted_current_card()
        if persisted is None:
            return
        try:
            updated = self.audio_service.remove_audio(persisted)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível remover", str(exc))
            return
        self._audio_generated(updated, success_message="Áudio removido do cartão.")

    def import_audio_batch(self) -> None:
        project = self.current_project
        if project is None or project.id is None or not project.uses_audio:
            return
        if self._pending_cards and not self.resolve_pending_changes("importar áudios em lote"):
            return
        selected_id = self.current_card.id if self.current_card is not None else None
        cards = self.database.list_cards(project.id)
        dialog = AudioBatchImportDialog(project, cards, self.audio_import_service, self)
        if not dialog.exec():
            return
        summary = dialog.summary
        if summary is not None:
            self.status.show_message(
                f"Importação em lote concluída: {summary.imported} áudio(s) associado(s), "
                f"{summary.skipped_existing} existente(s) ignorado(s).",
                error=bool(summary.errors),
            )
        self.populate_cards(select_card_id=selected_id)
        self.changed.emit()

    def _audio_generated(self, card: object, success_message: str = "Áudio gerado, arquivo validado e associado ao cartão.") -> None:
        if not isinstance(card, FlashcardData):
            return
        self.current_card = self._merge_media_into_draft(card)
        card_id = self.current_card.id
        ok, missing = self.audio_service.audio_status(self.current_project, self.current_card)
        if ok:
            self.status.show_message(success_message)
        elif not self.current_card.audio_path and success_message.startswith("Áudio removido"):
            self.status.show_message(success_message)
        else:
            self.status.show_message("A geração terminou, mas ainda faltam: " + ", ".join(missing), error=True)
        self.populate_cards(select_card_id=card_id)
        self.changed.emit()

    def generate_all_audio(self) -> None:
        project = self.current_project
        if project is None or project.id is None or not project.uses_audio:
            return
        if self._pending_cards and not self.resolve_pending_changes("gerar áudios em lote"):
            return
        cards = [
            card for card in self.database.list_cards(project.id)
            if project.card_uses_component(card, "audio")
        ]
        if not cards:
            return
        if QMessageBox.question(
            self,
            "Gerar áudios",
            f"Gerar os áudios ausentes de {len(cards)} cartões que utilizam Áudio? Serviços por API podem consumir sua cota.",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.bulk_audio_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.status.show_message("Preparando geração de áudios...")

        def run_all() -> tuple[int, int, list[str]]:
            completed = 0
            existing = 0
            errors: list[str] = []
            total = len(cards)
            for index, card in enumerate(cards, start=1):
                worker.signals.progress.emit(
                    int((index - 1) * 100 / total),
                    json.dumps({"kind": "audio", "state": "working", "card_id": card.id, "word": card.word, "index": index, "total": total}, ensure_ascii=False),
                )
                before_ok, _ = self.audio_service.audio_status(project, card)
                if before_ok:
                    existing += 1
                    state = "existing"
                else:
                    try:
                        updated = self.audio_service.generate_for_card(project, card)
                        ok, missing = self.audio_service.audio_status(project, updated)
                        if not ok:
                            raise RuntimeError("faltam " + ", ".join(missing))
                        completed += 1
                        state = "done"
                    except Exception as exc:
                        errors.append(f"{card.word}: {exc}")
                        state = "error"
                worker.signals.progress.emit(
                    int(index * 100 / total),
                    json.dumps({"kind": "audio", "state": state, "card_id": card.id, "word": card.word, "index": index, "total": total}, ensure_ascii=False),
                )
            return completed, existing, errors

        worker = Worker(run_all)
        worker.signals.progress.connect(self._bulk_media_progress)
        worker.signals.result.connect(self._bulk_audio_finished)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self._update_action_states())
        self._keep_worker(worker)

    def _bulk_audio_finished(self, result: object) -> None:
        completed, existing, errors = result
        self.progress.setValue(100)
        if errors:
            self.status.show_message(
                f"Geração concluída: {completed} cartões receberam áudio, {existing} já estavam completos e {len(errors)} falharam. Primeira falha: {errors[0]}",
                error=True,
            )
        else:
            self.status.show_message(
                f"Geração concluída: {completed} cartões receberam áudio e {existing} já estavam completos."
            )
        self.populate_cards()
        self.changed.emit()

    def _export_cards(self, cards: list[FlashcardData], title: str) -> None:
        if self.current_project is None:
            return
        if not cards:
            QMessageBox.warning(self, "Nada selecionado", "Selecione ao menos um cartão para exportar.")
            return
        last_dir = Path(self.database.get_setting("last_export_dir", str(self.paths.downloads_dir)))
        if not last_dir.is_dir():
            last_dir = self.paths.downloads_dir
        filename, _ = QFileDialog.getSaveFileName(
            self,
            title,
            str(last_dir / f"{self.current_project.name}.apkg"),
            "Pacote do Anki (*.apkg)",
        )
        if not filename:
            return
        try:
            errors, warnings = self.export_service.analyze_cards(self.current_project, cards)
            if errors:
                raise ValueError(
                    "Alguns cartões ficariam sem conteúdo na frente:\n\n"
                    + "\n".join(f"• {item}" for item in errors[:8])
                    + ("\n..." if len(errors) > 8 else "")
                )
            if warnings:
                preview = "\n".join(f"• {item}" for item in warnings[:8])
                suffix = "\n..." if len(warnings) > 8 else ""
                answer = QMessageBox.question(
                    self,
                    "Mídias ou campos ausentes",
                    f"{len(warnings)} cartão(ões) possuem componentes ausentes. "
                    "Os componentes vazios serão omitidos e o restante será exportado normalmente.\n\n"
                    f"{preview}{suffix}\n\nContinuar com a exportação?",
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            output = self.export_service.export(self.current_project, cards, Path(filename))
        except Exception as exc:
            QMessageBox.critical(self, "Falha na exportação", str(exc))
            return
        self.database.set_setting("last_export_dir", str(Path(output).parent))
        QMessageBox.information(
            self,
            "Exportação concluída",
            f"{len(cards)} cartões foram gravados no pacote:\n{output}\n\n"
            "Se o Anki mostrar menos cartões novos na tela de estudo, confira o limite diário de Novos nas opções do baralho.",
        )

    def export_selected(self) -> None:
        if self.current_project is None or self.current_project.id is None:
            return
        if not self.resolve_pending_changes("exportar os cartões selecionados"):
            return
        cards = self.database.list_cards_by_ids(self.current_project.id, self.checked_card_ids())
        self._export_cards(cards, "Exportar cartões selecionados")

    def export_project(self) -> None:
        if self.current_project is None or self.current_project.id is None:
            QMessageBox.warning(self, "Sem projeto", "Selecione um projeto para exportar.")
            return
        if not self.resolve_pending_changes("exportar o projeto"):
            return
        cards = self.database.list_cards(self.current_project.id)
        self._export_cards(cards, "Exportar todos os cartões")
