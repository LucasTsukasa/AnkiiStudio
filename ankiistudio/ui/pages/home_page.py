from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ankiistudio.constants import TEMPLATE_LABELS, language_label
from ankiistudio.database import Database
from ankiistudio.ui.design_system import responsive_columns
from ankiistudio.ui.widgets import ActionCard, PageHeader, PageScrollArea, SectionCard


class HomePage(QWidget):
    create_requested = Signal()
    import_requested = Signal()
    projects_requested = Signal()

    def __init__(self, database: Database, resource_dir: Path) -> None:
        super().__init__()
        self.database = database
        self.resource_dir = resource_dir

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)
        self.content_layout = layout
        layout.addWidget(
            PageHeader(
                "Bem-vindo ao BenkyouStudio",
                "Transforme conteúdos em materiais de estudo, organize seus flashcards e prepare seus baralhos para o Anki.",
            )
        )

        self.action_grid = QGridLayout()
        self.action_grid.setHorizontalSpacing(12)
        self.action_grid.setVerticalSpacing(12)
        icon_dir = resource_dir / "icons"
        create_card = ActionCard(
            "Criar novo projeto",
            "Selecione o idioma, defina a estrutura do cartão e escolha a origem do conteúdo.",
            "Começar",
            icon_dir / "create_active.svg",
        )
        import_card = ActionCard(
            "Importar de uma IA",
            "Use o prompt estruturado do BenkyouStudio e importe o conteúdo produzido por uma IA.",
            "Abrir importação",
            icon_dir / "import_active.svg",
        )
        projects_card = ActionCard(
            "Gerenciar projetos",
            "Revise cartões, processe mídias, organize subbaralhos e exporte arquivos .apkg.",
            "Ver projetos",
            icon_dir / "projects_active.svg",
        )
        create_card.clicked.connect(self.create_requested)
        import_card.clicked.connect(self.import_requested)
        projects_card.clicked.connect(self.projects_requested)
        self.action_cards = [create_card, import_card, projects_card]
        for card in self.action_cards:
            self.action_grid.addWidget(card, 0, 0)
        layout.addLayout(self.action_grid)

        recent = SectionCard("Projetos recentes", "Continue de onde parou.")
        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(220)
        self.recent_list.itemDoubleClicked.connect(lambda _: self.projects_requested.emit())
        recent.root.addWidget(self.recent_list)
        layout.addWidget(recent)
        layout.addStretch(1)

        self.page_scroll = PageScrollArea(content)
        self.page_scroll.viewport_resized.connect(lambda _width: self._apply_responsive_layout())
        root.addWidget(self.page_scroll)
        self._action_columns = 0
        self._apply_responsive_layout(force=True)
        self.refresh()

    def _available_content_width(self) -> int:
        viewport_width = self.page_scroll.viewport().width()
        if viewport_width <= 0:
            viewport_width = self.width()
        margins = self.content_layout.contentsMargins()
        return max(0, viewport_width - margins.left() - margins.right())

    def _apply_responsive_layout(self, *, force: bool = False) -> None:
        columns = responsive_columns(
            self._available_content_width(),
            item_min_width=260,
            maximum=3,
            spacing=self.action_grid.horizontalSpacing(),
        )
        if not force and columns == self._action_columns:
            return
        self._action_columns = columns
        for card in self.action_cards:
            self.action_grid.removeWidget(card)
        for index, card in enumerate(self.action_cards):
            self.action_grid.addWidget(card, index // columns, index % columns)

    def refresh(self) -> None:
        self.recent_list.clear()
        projects = self.database.list_projects()
        if not projects:
            self.recent_list.setMinimumHeight(124)
            self.recent_list.setMaximumHeight(124)
            item = QListWidgetItem(
                "Nenhum projeto criado ainda.\nSeus projetos recentes aparecerão aqui."
            )
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setSizeHint(QSize(0, 92))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.recent_list.addItem(item)
            return
        self.recent_list.setMinimumHeight(220)
        self.recent_list.setMaximumHeight(16777215)
        counts = self.database.project_card_counts()
        for project in projects[:10]:
            count = counts.get(int(project.id or 0), 0)
            label = TEMPLATE_LABELS.get(project.template_key, project.template_key)
            language = language_label(project.language)
            item = QListWidgetItem(f"{project.name}\n{language} · {label} · {count} cartões")
            item.setData(256, project.id)
            item.setSizeHint(QSize(0, 56))
            self.recent_list.addItem(item)
