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
from ankiistudio.models import FlashcardData, ProjectData
from ankiistudio.services.anki_export_service import AnkiExportService
from ankiistudio.services.audio_service import ProjectAudioService
from ankiistudio.services.image_service import ImageService
from ankiistudio.services.media_service import CardImageService
from ankiistudio.services.wikimedia_service import WikimediaService
from ankiistudio.ui.dialogs.image_search_dialog import ImageSearchDialog
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
        self.image_service = CardImageService(database, WikimediaService(), ImageService(paths.images_dir))
        self.audio_service = ProjectAudioService(database, paths)
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
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
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
        editor_card.root.addLayout(self.form)
        editor_content_layout.addWidget(editor_card)

        media_card = SectionCard(
            "Mídias",
            "As ações em massa processam apenas as mídias exigidas pela estrutura do projeto.",
        )
        media_row = QGridLayout()
        media_row.setHorizontalSpacing(8)
        media_row.setVerticalSpacing(8)
        self.image_button = QPushButton("Imagem deste cartão")
        self.bulk_image_button = QPushButton("Imagens para todos")
        self.audio_button = QPushButton("Áudio deste cartão")
        self.bulk_audio_button = QPushButton("Áudios para todos")
        self.save_button = QPushButton("Salvar alterações")
        for button in (self.image_button, self.bulk_image_button, self.audio_button, self.bulk_audio_button):
            button.setObjectName("SubtleButton")
        self.save_button.setObjectName("PrimaryButton")
        self.image_button.clicked.connect(self.search_image)
        self.bulk_image_button.clicked.connect(self.generate_all_images)
        self.audio_button.clicked.connect(self.generate_card_audio)
        self.bulk_audio_button.clicked.connect(self.generate_all_audio)
        self.save_button.clicked.connect(self.save_card)
        media_row.addWidget(self.image_button, 0, 0)
        media_row.addWidget(self.bulk_image_button, 0, 1)
        media_row.addWidget(self.audio_button, 1, 0)
        media_row.addWidget(self.bulk_audio_button, 1, 1)
        media_row.addWidget(self.save_button, 2, 0, 1, 2)
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
        selected = set(project.front_components + project.back_components)
        self._set_field_visible(self.section_combo, True)
        self._set_field_visible(self.word, True)
        self._set_field_visible(self.reading, "reading" in selected)
        self._set_field_visible(self.romanization, "romanization" in selected)
        self._set_field_visible(self.translation, "translation" in selected)
        self._set_field_visible(self.example, "example" in selected)
        self._set_field_visible(self.explanation, "explanation" in selected)
        self._set_field_visible(self.mnemonic, "mnemonic" in selected)

    def _update_action_states(self) -> None:
        has_project = self.current_project is not None and self.current_project.id is not None
        has_card = self.current_card is not None and self.current_card.id is not None
        for button in (
            self.export_selected_button,
            self.export_all_button,
            self.delete_project_button,
            self.add_card_button,
            self.select_all_button,
            self.select_none_button,
        ):
            button.setEnabled(has_project)
        self.delete_card_button.setEnabled(has_card)
        self.save_button.setEnabled(has_card)

        uses_images = bool(has_project and self.current_project and self.current_project.uses_images)
        uses_audio = bool(has_project and self.current_project and self.current_project.uses_audio)
        self.image_button.setEnabled(has_card and uses_images)
        self.bulk_image_button.setEnabled(has_project and uses_images)
        self.audio_button.setEnabled(has_card and uses_audio)
        self.bulk_audio_button.setEnabled(has_project and uses_audio)
        self.image_button.setToolTip("" if uses_images else "Este modelo não utiliza Imagem.")
        self.bulk_image_button.setToolTip("" if uses_images else "Este modelo não utiliza Imagem.")
        self.audio_button.setToolTip("" if uses_audio else "Este projeto não utiliza Áudio.")
        self.bulk_audio_button.setToolTip("" if uses_audio else "Este projeto não utiliza Áudio.")

    def refresh(self, select_project_id: int | None = None) -> None:
        current = select_project_id
        if current is None and self.current_project is not None:
            current = self.current_project.id
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        projects = self.database.list_projects()
        for project in projects:
            self.project_combo.addItem(project.name, project.id)
        self.project_combo.blockSignals(False)
        if not projects:
            self.current_project = None
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
        self.load_project()

    def load_project(self) -> None:
        project_id = self.project_combo.currentData()
        if project_id is None:
            return
        self.current_project = self.database.get_project(int(project_id))
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

    def populate_cards(self) -> None:
        checked_ids = set(self.checked_card_ids())
        had_rows = self.table.rowCount() > 0
        self.table.setRowCount(0)
        self.current_card = None
        self.clear_form()
        self._update_action_states()
        if self.current_project is None or self.current_project.id is None:
            return
        cards = self.database.list_cards(self.current_project.id)
        self.table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check_item.setCheckState(
                Qt.CheckState.Checked if (not had_rows or card.id in checked_ids) else Qt.CheckState.Unchecked
            )
            check_item.setData(Qt.ItemDataRole.UserRole, card.id)
            self.table.setItem(row, 0, check_item)

            image_ok = self.image_service.has_valid_image(card)
            audio_ok, _ = self.audio_service.audio_status(self.current_project, card) if self.current_project.uses_audio else (False, [])
            values = [
                card.section or "Principal",
                card.word,
                card.translation,
                "Sim" if image_ok else "Não",
                "Sim" if audio_ok else "Não",
            ]
            for column, value in enumerate(values, start=1):
                self.table.setItem(row, column, QTableWidgetItem(value))
        if cards:
            self.table.selectRow(0)
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
            return
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return
        card_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_card = self.database.get_card(int(card_id))
        if self.current_card:
            self.fill_form(self.current_card)
        self._update_action_states()

    def fill_form(self, card: FlashcardData) -> None:
        self._populate_section_combo(card.section)
        self.word.setText(card.word)
        self.reading.setText(card.reading)
        self.romanization.setText(card.romanization)
        self.translation.setText(card.translation)
        self.example.setText(card.example)
        self.explanation.setPlainText(card.explanation)
        self.mnemonic.setPlainText(card.mnemonic)
        self._apply_structure_visibility()

    def clear_form(self) -> None:
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

    def save_card(self) -> None:
        try:
            card = self.collect_card()
            self.database.update_card(card)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar", str(exc))
            return
        self.current_card = card
        self.status.show_message("Cartão salvo.")
        self.populate_cards()
        self.changed.emit()

    def add_card(self) -> None:
        if self.current_project is None or self.current_project.id is None:
            QMessageBox.warning(self, "Sem projeto", "Selecione um projeto.")
            return
        ids = self.database.add_cards(self.current_project.id, [FlashcardData(word="Novo cartão")])
        self.populate_cards()
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == ids[0]:
                self.table.selectRow(row)
                break
        self.changed.emit()

    def delete_card(self) -> None:
        if self.current_card is None or self.current_card.id is None:
            QMessageBox.warning(self, "Sem cartão", "Selecione um cartão para excluir.")
            return
        if QMessageBox.question(self, "Excluir cartão", f"Excluir o cartão “{self.current_card.word}”?",) != QMessageBox.StandardButton.Yes:
            return
        self.database.delete_card(self.current_card.id)
        self.populate_cards()
        self.changed.emit()

    def delete_project(self) -> None:
        if self.current_project is None or self.current_project.id is None:
            QMessageBox.warning(self, "Sem projeto", "Selecione um projeto para excluir.")
            return
        if QMessageBox.question(self, "Excluir projeto", f"Excluir o projeto “{self.current_project.name}” e todos os seus cartões?",) != QMessageBox.StandardButton.Yes:
            return
        self.database.delete_project(self.current_project.id)
        self.refresh()
        self.changed.emit()

    def search_image(self) -> None:
        if self.current_project is None or self.current_card is None:
            QMessageBox.warning(self, "Seleção necessária", "Selecione um cartão.")
            return
        if not self.current_project.uses_images:
            return
        term = self.current_card.word
        dialog = ImageSearchDialog(term, WikimediaService(), self)
        if not dialog.exec() or dialog.selected_result is None:
            return
        self.status.show_message("Baixando e otimizando a imagem...")
        worker = Worker(self.image_service.apply_wikimedia_image, self.current_project, self.current_card, dialog.selected_result)
        worker.signals.result.connect(self._image_applied)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        self._keep_worker(worker)

    def _image_applied(self, card: object) -> None:
        self.current_card = card
        self.status.show_message("Imagem associada e validada.")
        self.populate_cards()
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
        cards = self.database.list_cards(project.id)
        if not cards:
            return
        if QMessageBox.question(
            self,
            "Buscar imagens",
            f"Buscar automaticamente imagens ausentes para {len(cards)} cartões no Wikimedia Commons?",
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
                        self.image_service.apply_best_wikimedia_image(project, card)
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
        if self.current_project is None or self.current_card is None or not self.current_project.uses_audio:
            return
        self.status.show_message("Gerando apenas os áudios usados pela estrutura deste cartão...")
        worker = Worker(self.audio_service.generate_for_card, self.current_project, self.current_card)
        worker.signals.result.connect(self._audio_generated)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        self._keep_worker(worker)

    def _audio_generated(self, card: object) -> None:
        self.current_card = card
        ok, missing = self.audio_service.audio_status(self.current_project, card)
        if ok:
            self.status.show_message("Áudio gerado, arquivo validado e associado ao cartão.")
        else:
            self.status.show_message("A geração terminou, mas ainda faltam: " + ", ".join(missing), error=True)
        self.populate_cards()
        self.changed.emit()

    def generate_all_audio(self) -> None:
        project = self.current_project
        if project is None or project.id is None or not project.uses_audio:
            return
        cards = self.database.list_cards(project.id)
        if not cards:
            return
        if QMessageBox.question(
            self,
            "Gerar áudios",
            f"Gerar os áudios ausentes de {len(cards)} cartões? Serviços por API podem consumir sua cota.",
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
        cards = self.database.list_cards_by_ids(self.current_project.id, self.checked_card_ids())
        self._export_cards(cards, "Exportar cartões selecionados")

    def export_project(self) -> None:
        if self.current_project is None or self.current_project.id is None:
            QMessageBox.warning(self, "Sem projeto", "Selecione um projeto para exportar.")
            return
        cards = self.database.list_cards(self.current_project.id)
        self._export_cards(cards, "Exportar todos os cartões")
