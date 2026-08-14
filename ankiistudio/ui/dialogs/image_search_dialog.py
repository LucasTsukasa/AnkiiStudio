from __future__ import annotations

import html
from functools import partial
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, QSize, Slot, Qt, QThreadPool
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.i18n import tr
from ankiistudio.models import ImageSearchResult
from ankiistudio.services.image_sources import ImageSearchOutcome, ImageSearchService
from ankiistudio.ui.design_system.components import ASButton, ASDialog, ASLineEdit, ASCard
from ankiistudio.ui.workers import Worker


class _WorkerBridge(QObject):
    """Entrega callbacks de Worker sempre pela thread da interface Qt."""

    def __init__(self, on_result=None, on_error=None, on_finished=None) -> None:
        super().__init__()
        self.on_result = on_result
        self.on_error = on_error
        self.on_finished = on_finished

    @Slot(object)
    def result(self, payload: object) -> None:
        if self.on_result is not None:
            self.on_result(payload)

    @Slot(str)
    def error(self, message: str) -> None:
        if self.on_error is not None:
            self.on_error(message)

    @Slot()
    def finished(self) -> None:
        if self.on_finished is not None:
            self.on_finished()


class _SourceFilterMenu(QMenu):
    """Menu de seleção múltipla que permanece aberto ao marcar fontes."""

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        action = self.actionAt(event.position().toPoint())
        if action is not None and action.isEnabled() and action.isCheckable():
            action.setChecked(not action.isChecked())
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ImageSearchDialog(ASDialog):
    """Pesquisa manual de imagens para um único cartão.

    O termo original continua sendo a busca principal. Tradução, leitura,
    romanização e termos visuais aparecem como sugestões auxiliares. O filtro da
    janela restringe apenas a pesquisa atual e nunca altera as fontes globais das
    Configurações.
    """

    MAX_AUXILIARY_TERMS = 4
    AUXILIARY_RESULT_LIMIT = 6
    MAIN_RESULT_LIMIT = 12

    def __init__(
        self,
        initial_term: str,
        service: ImageSearchService,
        parent=None,
        *,
        auxiliary_terms: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.thread_pool = QThreadPool.globalInstance()
        self.results: list[ImageSearchResult] = []
        self.selected_result: ImageSearchResult | None = None
        self._workers: list[Worker] = []
        self._bridges: list[_WorkerBridge] = []
        self._closing = False
        self._main_generation = 0
        self._preview_generation = 0
        self._auxiliary_generation = 0
        self._auxiliary_terms = self._normalize_auxiliary_terms(initial_term, auxiliary_terms or [])
        self._auxiliary_lists: dict[str, QListWidget] = {}
        self._provider_actions: dict[str, QAction] = {}
        self._enabled_provider_keys = set(self.service.enabled_provider_keys())
        self._selected_provider_keys = set(self._enabled_provider_keys)
        self._filter_snapshot = set(self._selected_provider_keys)

        self.setWindowTitle("Pesquisar imagem")
        self.resize(1060, 760)
        self.setMinimumSize(820, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        main_label = QLabel("Busca principal")
        main_label.setObjectName("FieldLabel")
        root.addWidget(main_label)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = ASLineEdit(initial_term)
        self.search_input.setObjectName("ImageSearchInput")
        self.search_input.returnPressed.connect(self.search)

        self.filter_button = QToolButton()
        self.filter_button.setObjectName("ImageSourceFilterButton")
        self.filter_button.setFixedSize(40, 38)
        self.filter_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        filter_icon = Path(__file__).resolve().parents[2] / "resources" / "icons" / "filter.svg"
        if filter_icon.is_file():
            self.filter_button.setIcon(QIcon(str(filter_icon)))
            self.filter_button.setIconSize(QSize(18, 18))
        else:
            self.filter_button.setText("⌄")
        self._build_provider_filter_menu()

        self.search_button = ASButton("Pesquisar")
        self.search_button.setObjectName("PrimaryButton")
        self.search_button.clicked.connect(self.search)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.filter_button)
        search_row.addWidget(self.search_button)
        root.addLayout(search_row)

        self.warning_label = QLabel()
        self.warning_label.setObjectName("ImageSearchWarning")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        root.addWidget(self.warning_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        results_panel = ASCard()
        results_panel.setObjectName("ImageSearchPanel")
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(12, 12, 12, 12)
        results_layout.setSpacing(8)
        self.results_title = QLabel("Resultados principais")
        self.results_title.setObjectName("SectionTitle")
        results_layout.addWidget(self.results_title)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("ImageResultList")
        self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_widget.setMovement(QListView.Movement.Static)
        self.list_widget.setWrapping(True)
        self.list_widget.setWordWrap(True)
        self.list_widget.setSpacing(6)
        self.list_widget.setIconSize(QSize(150, 96))
        self.list_widget.setGridSize(QSize(190, 148))
        self.list_widget.currentRowChanged.connect(self.show_selected)
        results_layout.addWidget(self.list_widget, 1)
        splitter.addWidget(results_panel)

        details_panel = ASCard()
        details_panel.setObjectName("ImageSearchPanel")
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(9)
        selected_label = QLabel("Imagem selecionada")
        selected_label.setObjectName("SectionTitle")
        self.preview = QLabel("Selecione um resultado")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(280, 170)
        self.preview.setMaximumHeight(215)
        self.preview.setObjectName("ImagePreview")
        self.metadata = QLabel()
        self.metadata.setObjectName("ImageMetadata")
        self.metadata.setWordWrap(True)
        self.metadata.setOpenExternalLinks(True)
        self.metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.use_button = ASButton("Usar imagem selecionada")
        self.use_button.setObjectName("PrimaryButton")
        self.use_button.setEnabled(False)
        self.use_button.clicked.connect(self.accept_selected)
        details_layout.addWidget(selected_label)
        details_layout.addWidget(self.preview)
        details_layout.addWidget(self.metadata)
        details_layout.addStretch(1)
        details_layout.addWidget(self.use_button)
        splitter.addWidget(details_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([650, 360])
        root.addWidget(splitter, 1)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        divider.setObjectName("ImageSearchDivider")
        root.addWidget(divider)

        related_title = QLabel("Outras sugestões de busca")
        related_title.setObjectName("SectionTitle")
        root.addWidget(related_title)

        self.related_scroll = QScrollArea()
        self.related_scroll.setObjectName("ImageSuggestionScroll")
        self.related_scroll.setWidgetResizable(True)
        self.related_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.related_scroll.setMinimumHeight(150)
        self.related_scroll.setMaximumHeight(230)
        related_content = QWidget()
        self.related_layout = QVBoxLayout(related_content)
        self.related_layout.setContentsMargins(0, 0, 4, 0)
        self.related_layout.setSpacing(10)
        self.related_scroll.setWidget(related_content)
        root.addWidget(self.related_scroll)

        if not self._auxiliary_terms:
            empty = QLabel("Nenhum termo auxiliar disponível para este cartão.")
            empty.setObjectName("MutedLabel")
            self.related_layout.addWidget(empty)
        else:
            for term in self._auxiliary_terms:
                self._create_auxiliary_row(term)
            self.related_layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = ASButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        root.addLayout(buttons)

        if initial_term.strip():
            self.search()
        self._load_auxiliary_searches()

    @classmethod
    def _normalize_auxiliary_terms(cls, primary: str, values: list[str]) -> list[str]:
        result: list[str] = []
        seen = {" ".join(primary.casefold().split())}
        for raw in values:
            text = " ".join(str(raw or "").split())
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            result.append(text)
            if len(result) >= cls.MAX_AUXILIARY_TERMS:
                break
        return result

    def _build_provider_filter_menu(self) -> None:
        menu = _SourceFilterMenu(self)
        menu.addSection(tr("Fontes desta pesquisa"))
        for key in ImageSearchService.PROVIDER_KEYS:
            label = ImageSearchService.PROVIDER_LABELS[key]
            action = QAction(label, menu)
            action.setCheckable(True)
            enabled = key in self._enabled_provider_keys
            action.setEnabled(enabled)
            action.setChecked(enabled)
            if not enabled:
                action.setToolTip(tr("Fonte desativada nas Configurações"))
            action.toggled.connect(partial(self._provider_toggled, key))
            menu.addAction(action)
            self._provider_actions[key] = action
        menu.aboutToShow.connect(self._provider_filter_opened)
        menu.aboutToHide.connect(self._provider_filter_closed)
        self.filter_button.setMenu(menu)
        self._update_filter_tooltip()

    def _provider_filter_opened(self) -> None:
        self._filter_snapshot = set(self._selected_provider_keys)

    def _provider_toggled(self, key: str, checked: bool) -> None:
        if key not in self._enabled_provider_keys:
            return
        if checked:
            self._selected_provider_keys.add(key)
        else:
            self._selected_provider_keys.discard(key)
            if not self._selected_provider_keys:
                action = self._provider_actions[key]
                action.blockSignals(True)
                action.setChecked(True)
                action.blockSignals(False)
                self._selected_provider_keys.add(key)
        self._update_filter_tooltip()

    def _provider_filter_closed(self) -> None:
        if self._selected_provider_keys == self._filter_snapshot:
            return
        if self.search_input.text().strip():
            self.search()
        self._load_auxiliary_searches()

    def _update_filter_tooltip(self) -> None:
        labels = [
            ImageSearchService.PROVIDER_LABELS[key]
            for key in ImageSearchService.PROVIDER_KEYS
            if key in self._selected_provider_keys
        ]
        suffix = ", ".join(labels) if labels else tr("Nenhuma imagem")
        self.filter_button.setToolTip(f"{tr('Filtrar fontes')}: {suffix}")

    def _provider_filter(self) -> tuple[str, ...]:
        return tuple(
            key for key in ImageSearchService.PROVIDER_KEYS if key in self._selected_provider_keys
        )

    def _start_worker(
        self,
        worker: Worker,
        *,
        on_result=None,
        on_error=None,
        on_finished=None,
    ) -> None:
        self._workers.append(worker)
        bridge: _WorkerBridge

        def cleanup() -> None:
            if worker in self._workers:
                self._workers.remove(worker)
            if bridge in self._bridges:
                self._bridges.remove(bridge)
            if on_finished is not None:
                on_finished()

        bridge = _WorkerBridge(on_result, on_error, cleanup)
        self._bridges.append(bridge)
        worker.signals.result.connect(bridge.result)
        worker.signals.error.connect(bridge.error)
        worker.signals.finished.connect(bridge.finished)
        self.thread_pool.start(worker)

    def reject(self) -> None:  # type: ignore[override]
        self._closing = True
        super().reject()

    def accept(self) -> None:  # type: ignore[override]
        self._closing = True
        super().accept()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._closing = True
        super().closeEvent(event)

    def search(self) -> None:
        term = self.search_input.text().strip()
        if not term:
            QMessageBox.warning(self, tr("Pesquisa vazia"), tr("Informe um termo para pesquisar."))
            return
        provider_keys = self._provider_filter()
        if not provider_keys:
            QMessageBox.warning(
                self,
                tr("Fontes de imagem"),
                tr("Selecione ao menos uma fonte ativa para pesquisar."),
            )
            return
        self._main_generation += 1
        generation = self._main_generation
        self.search_button.setEnabled(False)
        self.list_widget.clear()
        self.results = []
        self.selected_result = None
        self.use_button.setEnabled(False)
        self.preview.clear()
        self.preview.setText(tr("Pesquisando..."))
        self.metadata.clear()
        self.warning_label.clear()
        self.warning_label.hide()
        self.results_title.setText(f"{tr('Resultados para')} “{term}”")

        worker = Worker(
            self.service.search_with_warnings,
            term,
            limit=self.MAIN_RESULT_LIMIT,
            provider_keys=provider_keys,
        )
        self._start_worker(
            worker,
            on_result=partial(self._main_results_ready, generation),
            on_error=partial(self._main_search_error, generation),
            on_finished=partial(self._main_search_finished, generation),
        )

    def _main_results_ready(self, generation: int, outcome: object) -> None:
        if self._closing or generation != self._main_generation:
            return
        if isinstance(outcome, ImageSearchOutcome):
            self.populate(outcome.results)
            if outcome.warnings:
                self.warning_label.setText(
                    tr("Algumas fontes apresentaram problemas") + ": " + " | ".join(outcome.warnings)
                )
                self.warning_label.show()
        else:
            self.populate(list(outcome) if outcome is not None else [])

    def _main_search_error(self, generation: int, message: str) -> None:
        if self._closing or generation != self._main_generation:
            return
        self.preview.setText(tr("Nenhuma imagem encontrada."))
        QMessageBox.critical(self, tr("Erro na pesquisa"), message)

    def _main_search_finished(self, generation: int) -> None:
        if self._closing or generation != self._main_generation:
            return
        self.search_button.setEnabled(True)

    def populate(self, results: list[ImageSearchResult]) -> None:
        if self._closing:
            return
        self.results = list(results)
        self.list_widget.clear()
        for result in self.results:
            source = ImageSearchService.PROVIDER_LABELS.get(result.provider, result.provider or tr("Fonte"))
            title = result.title.strip() or source
            if len(title) > 48:
                title = title[:45].rstrip() + "…"
            item = QListWidgetItem(f"{title}\n{source}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            item.setToolTip(
                f"{result.title}\n{source}\n{result.license_name or tr('licença não identificada')}"
            )
            item.setSizeHint(QSize(190, 148))
            self.list_widget.addItem(item)
            url = result.thumbnail_url or result.file_url
            if url:
                worker = Worker(self.service.download, url)
                self._start_worker(
                    worker,
                    on_result=partial(self._main_thumbnail_ready, item),
                )
        if self.results:
            self.list_widget.setCurrentRow(0)
        else:
            self.preview.setText(tr("Nenhuma imagem encontrada."))

    def _main_thumbnail_ready(self, item: QListWidgetItem, payload: object) -> None:
        if self._closing or item.listWidget() is not self.list_widget:
            return
        raw, _ = payload
        pixmap = QPixmap()
        if not pixmap.loadFromData(QByteArray(raw)) or pixmap.isNull():
            return
        item.setIcon(
            QIcon(
                pixmap.scaled(
                    QSize(150, 96),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        )

    def show_selected(self, index: int) -> None:
        if self._closing or index < 0 or index >= len(self.results):
            return
        self._select_result(self.results[index])

    def _select_result(self, result: ImageSearchResult) -> None:
        if self._closing:
            return
        self.selected_result = result
        self.use_button.setEnabled(True)
        self._set_metadata(result)
        url = result.thumbnail_url or result.file_url
        if not url:
            self.preview.setText(tr("Não foi possível carregar a miniatura."))
            return
        self._preview_generation += 1
        generation = self._preview_generation
        self.preview.clear()
        self.preview.setText(tr("Pesquisando..."))
        worker = Worker(self.service.download, url)
        self._start_worker(
            worker,
            on_result=partial(self._preview_ready, generation),
            on_error=partial(self._preview_error, generation),
        )

    def _set_metadata(self, result: ImageSearchResult) -> None:
        source = ImageSearchService.PROVIDER_LABELS.get(result.provider, result.provider or tr("Fonte"))
        source_html = html.escape(source)
        if result.description_url.startswith("https://"):
            source_html = f'<a href="{html.escape(result.description_url, quote=True)}">{source_html}</a>'
        license_html = html.escape(result.license_name or tr("não identificada"))
        if result.license_url.startswith("https://"):
            license_html = f'<a href="{html.escape(result.license_url, quote=True)}">{license_html}</a>'
        self.metadata.setText(
            f"<b>{html.escape(result.title)}</b><br><br>"
            f"<b>{tr('Fonte')}</b><br>{source_html}<br><br>"
            f"<b>{tr('Autor')}</b><br>{html.escape(result.author or tr('não informado'))}<br><br>"
            f"<b>{tr('Licença')}</b><br>{license_html}<br><br>"
            f"<b>{tr('Dimensões')}</b><br>{result.width or '?'} × {result.height or '?'}"
        )

    def _preview_ready(self, generation: int, payload: object) -> None:
        if self._closing or generation != self._preview_generation:
            return
        self.set_preview(payload)

    def _preview_error(self, generation: int, _message: str) -> None:
        if self._closing or generation != self._preview_generation:
            return
        self.preview.setText(tr("Não foi possível carregar a miniatura."))

    def set_preview(self, payload: object) -> None:
        if self._closing:
            return
        raw, _ = payload
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(raw))
        if pixmap.isNull():
            self.preview.setText(tr("Formato de imagem não suportado na prévia."))
            return
        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _create_auxiliary_row(self, term: str) -> None:
        container = ASCard(variant="interactive")
        container.setObjectName("ImageSuggestionRow")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)
        label = QLabel(f"{tr('Resultados para')} “{term}”")
        label.setObjectName("FieldLabel")
        list_widget = QListWidget()
        list_widget.setObjectName("ImageSuggestionList")
        list_widget.setViewMode(QListView.ViewMode.IconMode)
        list_widget.setFlow(QListView.Flow.LeftToRight)
        list_widget.setWrapping(False)
        list_widget.setResizeMode(QListView.ResizeMode.Adjust)
        list_widget.setMovement(QListView.Movement.Static)
        list_widget.setIconSize(QSize(104, 68))
        list_widget.setGridSize(QSize(148, 102))
        list_widget.setMinimumHeight(108)
        list_widget.setMaximumHeight(112)
        list_widget.itemClicked.connect(self._auxiliary_item_clicked)
        layout.addWidget(label)
        layout.addWidget(list_widget)
        self.related_layout.addWidget(container)
        self._auxiliary_lists[term] = list_widget

    def _load_auxiliary_searches(self) -> None:
        self._auxiliary_generation += 1
        generation = self._auxiliary_generation
        provider_keys = self._provider_filter()
        for term, widget in self._auxiliary_lists.items():
            widget.clear()
            if not provider_keys:
                continue
            worker = Worker(
                self.service.search_with_warnings,
                term,
                limit=self.AUXILIARY_RESULT_LIMIT,
                provider_keys=provider_keys,
            )
            self._start_worker(
                worker,
                on_result=partial(self._auxiliary_results_ready, term, generation),
                on_error=partial(self._auxiliary_search_error, term, generation),
            )

    def _auxiliary_search_error(self, term: str, generation: int, message: str) -> None:
        if self._closing or generation != self._auxiliary_generation:
            return
        widget = self._auxiliary_lists.get(term)
        if widget is None:
            return
        widget.clear()
        item = QListWidgetItem(message)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        widget.addItem(item)

    def _auxiliary_results_ready(self, term: str, generation: int, outcome: object) -> None:
        if self._closing or generation != self._auxiliary_generation:
            return
        widget = self._auxiliary_lists.get(term)
        if widget is None:
            return
        widget.clear()
        results = outcome.results if isinstance(outcome, ImageSearchOutcome) else list(outcome or [])
        if not results:
            item = QListWidgetItem(tr("Nenhuma imagem encontrada."))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            widget.addItem(item)
            return
        for result in results[: self.AUXILIARY_RESULT_LIMIT]:
            source = ImageSearchService.PROVIDER_LABELS.get(result.provider, result.provider or tr("Fonte"))
            title = result.title.strip() or source
            if len(title) > 32:
                title = title[:29].rstrip() + "…"
            item = QListWidgetItem(f"{title}\n{source}")
            item.setToolTip(f"{result.title}\n{source}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            widget.addItem(item)
            url = result.thumbnail_url or result.file_url
            if url:
                worker = Worker(self.service.download, url)
                self._start_worker(
                    worker,
                    on_result=partial(self._auxiliary_thumbnail_ready, widget, item),
                )

    def _auxiliary_thumbnail_ready(self, widget: QListWidget, item: QListWidgetItem, payload: object) -> None:
        if self._closing or item.listWidget() is not widget:
            return
        raw, _ = payload
        pixmap = QPixmap()
        if not pixmap.loadFromData(QByteArray(raw)) or pixmap.isNull():
            return
        item.setIcon(
            QIcon(
                pixmap.scaled(
                    QSize(104, 68),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        )

    def _auxiliary_item_clicked(self, item: QListWidgetItem) -> None:
        result = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(result, ImageSearchResult):
            self._select_result(result)

    def accept_selected(self) -> None:
        if self.selected_result is None:
            QMessageBox.warning(self, tr("Nenhuma imagem"), tr("Selecione uma imagem."))
            return
        self.accept()
