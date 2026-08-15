from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import AppPaths
from ankiistudio.database import Database
from ankiistudio.i18n import current_language, language_display_name, tr
from ankiistudio.models import ProjectData
from ankiistudio.services.project_service import ProjectService
from ankiistudio.ui.design_system import responsive_columns
from ankiistudio.ui.design_system.components import ASButton, ASCard, ASComboBox, ASContextMenu, ASLineEdit, ASTabWidget
from ankiistudio.ui.widgets import PageHeader


class ProjectCard(ASCard):
    CARD_WIDTH = 238
    CARD_HEIGHT = 292

    open_requested = Signal(int)
    duplicate_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, project: ProjectData, card_count: int) -> None:
        super().__init__(variant="interactive")
        self.project = project
        self.setObjectName("ProjectCard")
        self.setProperty("asComponent", "project-card")
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 15, 14, 14)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        title = ASButton(project.name, variant="ghost")
        title.setObjectName("ProjectCardButton")
        title.setToolTip(project.name)
        title.clicked.connect(lambda: self.open_requested.emit(int(project.id or 0)))
        menu_button = QToolButton()
        menu_button.setObjectName("ProjectCardMenuButton")
        menu_button.setText("⋮")
        menu_button.setFixedSize(28, 28)
        menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        menu_button.setToolTip("Opções do projeto")
        menu_button.clicked.connect(lambda: self._show_menu(menu_button.mapToGlobal(menu_button.rect().bottomLeft())))
        top.addWidget(title, 1)
        top.addWidget(menu_button)
        layout.addLayout(top)

        card_word = tr("cartão" if card_count == 1 else "cartões")
        meta = QLabel(f"{language_display_name(project.language)} · {card_count} {card_word}")
        meta.setObjectName("MutedLabel")
        layout.addWidget(meta)
        layout.addSpacing(8)
        if project.topic.strip():
            topic = QLabel(project.topic.strip())
            topic.setWordWrap(True)
            topic.setObjectName("ProjectTopic")
            topic.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            topic.setMaximumHeight(66)
            topic.setToolTip(project.topic.strip())
            layout.addWidget(topic)
        layout.addStretch(1)
        updated = QLabel(f"{tr('Atualizado em')} {self._formatted_date(project.updated_at)}")
        updated.setObjectName("MutedLabel")
        layout.addWidget(updated)

    @staticmethod
    def _formatted_date(value: str) -> str:
        raw = (value or "")[:10]
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            return raw
        if current_language() == "pt_BR":
            return parsed.strftime("%d/%m/%Y")
        return parsed.strftime("%Y-%m-%d")

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.project.id is not None:
            self.open_requested.emit(self.project.id)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        super().mouseDoubleClickEvent(event)

    def _context_menu(self, pos) -> None:
        self._show_menu(self.mapToGlobal(pos))

    def _show_menu(self, global_pos) -> None:
        project_id = int(self.project.id or 0)
        menu = ASContextMenu(self)
        open_action = menu.addAction(tr("Abrir"))
        duplicate_action = menu.addAction(tr("Duplicar"))
        menu.addSeparator()
        delete_action = menu.addAction(tr("Excluir"))
        chosen = menu.exec(global_pos)
        if chosen is open_action:
            self.open_requested.emit(project_id)
        elif chosen is duplicate_action:
            self.duplicate_requested.emit(project_id)
        elif chosen is delete_action:
            self.delete_requested.emit(project_id)


class ProjectsHubPage(QWidget):
    """Biblioteca visual de projetos com ferramentas do projeto reunidas em um só lugar."""

    changed = Signal()

    def __init__(self, database: Database, paths: AppPaths) -> None:
        super().__init__()
        self.database = database
        self.paths = paths
        self.project_service = ProjectService(database)
        self._current_project_id: int | None = None
        self._grid_columns = 0
        self._cards: list[ProjectCard] = []
        self._empty_label: QLabel | None = None
        self._filters_compact: bool | None = None
        self._detail_tools_ready = False
        self.cards_page = None
        self.models_page = None
        self.audio_panel = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self.refresh_library)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.library_page = QWidget()
        library = QVBoxLayout(self.library_page)
        library.setContentsMargins(24, 22, 24, 22)
        library.setSpacing(14)
        library.addWidget(PageHeader("Projetos", "Sua biblioteca de flashcards e materiais em criação."))
        self.filters_layout = QGridLayout()
        self.filters_layout.setHorizontalSpacing(10)
        self.filters_layout.setVerticalSpacing(8)
        self.search_input = ASLineEdit()
        self.search_input.setPlaceholderText("Pesquisar projetos...")
        self.search_input.textChanged.connect(self._schedule_library_refresh)
        self.language_filter = ASComboBox()
        self.language_filter.currentIndexChanged.connect(self.refresh_library)
        self.sort_combo = ASComboBox()
        self.sort_combo.addItem("Mais recentes", "recent")
        self.sort_combo.addItem("Nome A–Z", "name")
        self.sort_combo.addItem("Mais cartões", "cards")
        self.sort_combo.currentIndexChanged.connect(self.refresh_library)
        for widget in (self.search_input, self.language_filter, self.sort_combo):
            self.filters_layout.addWidget(widget, 0, 0)
        library.addLayout(self.filters_layout)

        self.library_scroll = QScrollArea()
        self.library_scroll.setWidgetResizable(True)
        self.library_scroll.setObjectName("PageScroll")
        self.library_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_surface = QWidget()
        self.cards_surface.setObjectName("PageSurface")
        self.cards_grid = QGridLayout(self.cards_surface)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setHorizontalSpacing(12)
        self.cards_grid.setVerticalSpacing(12)
        self.cards_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.library_scroll.setWidget(self.cards_surface)
        library.addWidget(self.library_scroll, 1)
        self.stack.addWidget(self.library_page)

        self.detail_page = QWidget()
        detail = QVBoxLayout(self.detail_page)
        detail.setContentsMargins(18, 16, 18, 18)
        detail.setSpacing(10)
        header = QHBoxLayout()
        back = ASButton("← Projetos", variant="ghost")
        back.setObjectName("SubtleButton")
        back.clicked.connect(self.show_library)
        self.detail_title = QLabel()
        self.detail_title.setObjectName("PageTitle")
        header.addWidget(back)
        header.addWidget(self.detail_title, 1)
        detail.addLayout(header)
        self.tabs = ASTabWidget()
        detail.addWidget(self.tabs, 1)
        self.stack.addWidget(self.detail_page)
        self._apply_filters_layout(force=True)
        self.show_library()

    def _schedule_library_refresh(self, *_args) -> None:
        self._search_timer.start()

    def _ensure_detail_tools(self) -> None:
        if self._detail_tools_ready:
            return
        from ankiistudio.ui.pages.models_page import ModelsPage
        from ankiistudio.ui.pages.projects_page import ProjectsPage
        from ankiistudio.ui.panels import ProjectAudioSettingsPanel

        database = self.database
        paths = self.paths
        self.cards_page = ProjectsPage(database, paths, embedded=True)
        self.models_page = ModelsPage(database, embedded=True)
        self.audio_panel = ProjectAudioSettingsPanel(database, paths)
        self.tabs.addTab(self.cards_page, "Cartões")
        self.tabs.addTab(self.models_page, "Estrutura e aparência")
        self.tabs.addTab(self.audio_panel, "Áudio do projeto")
        self.cards_page.changed.connect(self._child_changed)
        self._detail_tools_ready = True

    def show_library(self) -> None:
        if self.cards_page is not None and not self.cards_page.resolve_pending_changes("voltar à biblioteca de projetos"):
            return
        self._current_project_id = None
        self.refresh_library()
        self.stack.setCurrentWidget(self.library_page)

    def open_project(self, project_id: int) -> None:
        project = self.database.get_project(project_id)
        if project is None:
            self.refresh_library()
            return
        self._ensure_detail_tools()
        assert self.cards_page is not None and self.models_page is not None and self.audio_panel is not None
        if not self.cards_page.resolve_pending_changes("abrir outro projeto"):
            return
        self._current_project_id = project_id
        self.detail_title.setText(project.name)
        self.cards_page.select_project(project_id)
        self.models_page.set_project(project_id)
        self.audio_panel.set_project(project_id)
        self.stack.setCurrentWidget(self.detail_page)

    def refresh(self, select_project_id: int | None = None) -> None:
        self.refresh_library()
        if select_project_id is not None:
            self.open_project(select_project_id)
        elif self._current_project_id is not None:
            project = self.database.get_project(self._current_project_id)
            if project is not None and self.cards_page is not None and self.models_page is not None and self.audio_panel is not None:
                self.detail_title.setText(project.name)
                self.cards_page.select_project(project.id)
                self.models_page.refresh()
                self.models_page.set_project(project.id)
                self.audio_panel.set_project(project.id)

    def retranslate_ui(self) -> None:
        """Atualiza textos dinâmicos dos cards sem tocar no estado do editor."""
        self.refresh_library()

    def refresh_audio_profiles(self) -> None:
        """Reflete perfis globais novos/editados no projeto que já está aberto."""
        if self.audio_panel is not None:
            self.audio_panel.refresh_audio_profiles()

    def refresh_library(self, *_args) -> None:
        projects = self.database.list_projects()
        selected_language = self.language_filter.currentData() if self.language_filter.count() else None
        languages = sorted({p.language for p in projects}, key=language_display_name)
        current_lang = selected_language
        self.language_filter.blockSignals(True)
        self.language_filter.clear()
        self.language_filter.addItem("Todos os idiomas", None)
        for code in languages:
            self.language_filter.addItem(language_display_name(code), code)
        if current_lang:
            idx = self.language_filter.findData(current_lang)
            if idx >= 0:
                self.language_filter.setCurrentIndex(idx)
        self.language_filter.blockSignals(False)

        query = self.search_input.text().strip().casefold()
        language = self.language_filter.currentData()
        counts = self.database.project_card_counts()
        filtered = [
            p for p in projects
            if (not query or query in p.name.casefold() or query in p.topic.casefold())
            and (language is None or p.language == language)
        ]
        sort_key = str(self.sort_combo.currentData() or "recent")
        if sort_key == "name":
            filtered.sort(key=lambda p: p.name.casefold())
        elif sort_key == "cards":
            filtered.sort(key=lambda p: counts.get(int(p.id or 0), 0), reverse=True)
        else:
            filtered.sort(key=lambda p: (p.updated_at, p.id or 0), reverse=True)
        self._rebuild_cards(filtered, counts)

    def _rebuild_cards(self, projects: list[ProjectData], counts: dict[int, int]) -> None:
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()
        self._empty_label = None
        columns = responsive_columns(
            self.library_scroll.viewport().width(),
            item_min_width=ProjectCard.CARD_WIDTH,
            maximum=5,
            spacing=self.cards_grid.horizontalSpacing(),
        )
        self._grid_columns = columns
        for column in range(6):
            self.cards_grid.setColumnStretch(column, 0)
        self.cards_grid.setColumnStretch(columns, 1)
        for index, project in enumerate(projects):
            card = ProjectCard(project, counts.get(int(project.id or 0), 0))
            card.open_requested.connect(self.open_project)
            card.duplicate_requested.connect(self.duplicate_project)
            card.delete_requested.connect(self.delete_project)
            self.cards_grid.addWidget(
                card,
                index // columns,
                index % columns,
                alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            )
            self._cards.append(card)
        if not projects:
            empty = QLabel("Nenhum projeto encontrado. Crie um novo projeto para começar.")
            empty.setObjectName("PageSubtitle")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_grid.addWidget(empty, 0, 0)
            self._empty_label = empty

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_filters_layout()
        if self.stack.currentWidget() is self.library_page:
            columns = responsive_columns(
                self.library_scroll.viewport().width(),
                item_min_width=ProjectCard.CARD_WIDTH,
                maximum=5,
                spacing=self.cards_grid.horizontalSpacing(),
            )
            if columns != self._grid_columns:
                self._relayout_cards(columns)

    def _relayout_cards(self, columns: int) -> None:
        columns = max(1, int(columns))
        if columns == self._grid_columns:
            return
        self._grid_columns = columns
        while self.cards_grid.count():
            self.cards_grid.takeAt(0)
        for column in range(6):
            self.cards_grid.setColumnStretch(column, 0)
        self.cards_grid.setColumnStretch(columns, 1)
        if self._cards:
            for index, card in enumerate(self._cards):
                self.cards_grid.addWidget(
                    card,
                    index // columns,
                    index % columns,
                    alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                )
        elif self._empty_label is not None:
            self.cards_grid.addWidget(self._empty_label, 0, 0)

    def _apply_filters_layout(self, *, force: bool = False) -> None:
        filter_width = self.library_scroll.viewport().width()
        if filter_width <= 0:
            filter_width = self.width()
        compact = filter_width < 760
        if not force and compact == self._filters_compact:
            return
        self._filters_compact = compact
        for widget in (self.search_input, self.language_filter, self.sort_combo):
            self.filters_layout.removeWidget(widget)
        if compact:
            self.filters_layout.addWidget(self.search_input, 0, 0, 1, 2)
            self.filters_layout.addWidget(self.language_filter, 1, 0)
            self.filters_layout.addWidget(self.sort_combo, 1, 1)
        else:
            self.filters_layout.addWidget(self.search_input, 0, 0)
            self.filters_layout.addWidget(self.language_filter, 0, 1)
            self.filters_layout.addWidget(self.sort_combo, 0, 2)
            self.filters_layout.setColumnStretch(0, 1)

    def duplicate_project(self, project_id: int) -> None:
        project = self.database.get_project(project_id)
        if project is None:
            return
        try:
            new_id = self.project_service.duplicate_project(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível duplicar", str(exc))
            return
        self.refresh_library()
        self.changed.emit()
        self.open_project(new_id)

    def delete_project(self, project_id: int) -> None:
        project = self.database.get_project(project_id)
        if project is None:
            return
        if QMessageBox.question(
            self,
            "Excluir projeto",
            f"Excluir o projeto “{project.name}” e todos os seus cartões?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.database.delete_project(project_id)
        self.refresh_library()
        self.changed.emit()
        if self._current_project_id == project_id:
            self.show_library()

    def confirm_close(self) -> bool:
        return self.cards_page.confirm_close() if self.cards_page is not None else True

    def resolve_pending_changes(self, action: str) -> bool:
        return self.cards_page.resolve_pending_changes(action) if self.cards_page is not None else True

    def _child_changed(self) -> None:
        if self._current_project_id is not None and self.models_page is not None and self.audio_panel is not None:
            project = self.database.get_project(self._current_project_id)
            if project is not None:
                self.detail_title.setText(project.name)
                self.models_page.refresh()
                self.models_page.set_project(project.id)
                self.audio_panel.set_project(project.id)
        self.refresh_library()
        self.changed.emit()
