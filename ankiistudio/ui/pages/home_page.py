from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ankiistudio.constants import TEMPLATE_LABELS, language_label
from ankiistudio.database import Database
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
        layout.addWidget(
            PageHeader(
                "Bem-vindo ao AnkiiStudio",
                "Crie, organize e exporte flashcards com estrutura personalizada, imagens e áudio.",
            )
        )

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        icon_dir = resource_dir / "icons"
        create_card = ActionCard(
            "Criar novo projeto",
            "Selecione o idioma, defina a estrutura do cartão e escolha a origem do conteúdo.",
            "Começar",
            icon_dir / "create_active.svg",
        )
        import_card = ActionCard(
            "Importar de uma IA",
            "Use o prompt estruturado do AnkiiStudio e importe o conteúdo produzido por uma IA.",
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
        cards.addWidget(create_card, 0, 0)
        cards.addWidget(import_card, 0, 1)
        cards.addWidget(projects_card, 0, 2)
        layout.addLayout(cards)

        recent = SectionCard("Projetos recentes", "Continue de onde parou.")
        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(220)
        self.recent_list.itemDoubleClicked.connect(lambda _: self.projects_requested.emit())
        recent.root.addWidget(self.recent_list)
        layout.addWidget(recent)
        layout.addStretch(1)

        root.addWidget(PageScrollArea(content))
        self.refresh()

    def refresh(self) -> None:
        self.recent_list.clear()
        projects = self.database.list_projects()
        if not projects:
            item = QListWidgetItem("Nenhum projeto criado ainda.")
            self.recent_list.addItem(item)
            return
        for project in projects[:10]:
            count = len(self.database.list_cards(int(project.id)))
            label = TEMPLATE_LABELS.get(project.template_key, project.template_key)
            language = language_label(project.language)
            item = QListWidgetItem(f"{project.name}\n{language} · {label} · {count} cartões")
            item.setData(256, project.id)
            item.setSizeHint(QSize(0, 56))
            self.recent_list.addItem(item)
