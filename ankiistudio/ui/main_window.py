from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import AppPaths
from ankiistudio.constants import APP_NAME, APP_VERSION
from ankiistudio.database import Database
from ankiistudio.ui.pages.about_page import AboutPage
from ankiistudio.ui.pages.audio_page import AudioPage
from ankiistudio.ui.pages.create_page import CreatePage
from ankiistudio.ui.pages.home_page import HomePage
from ankiistudio.ui.pages.models_page import ModelsPage
from ankiistudio.ui.pages.projects_page import ProjectsPage
from ankiistudio.ui.pages.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self, database: Database, paths: AppPaths, resource_dir: Path) -> None:
        super().__init__()
        self.database = database
        self.paths = paths
        self.resource_dir = resource_dir
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1120, 720)
        self.setMinimumSize(960, 620)
        icon_path = resource_dir / "icons" / "app.png"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(196)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 12)
        sidebar_layout.setSpacing(4)

        brand_panel = QFrame()
        brand_panel.setObjectName("BrandPanel")
        brand_layout = QHBoxLayout(brand_panel)
        brand_layout.setContentsMargins(8, 8, 8, 18)
        brand_layout.setSpacing(9)
        mark = QLabel()
        logo_path = resource_dir / "icons" / "app.png"
        if logo_path.is_file():
            mark.setPixmap(QIcon(str(logo_path)).pixmap(QSize(24, 24)))
        mark.setFixedSize(26, 26)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand = QLabel("AnkiiStudio")
        brand.setObjectName("Brand")
        brand_layout.addWidget(mark)
        brand_layout.addWidget(brand)
        brand_layout.addStretch(1)
        sidebar_layout.addWidget(brand_panel)

        self.stack = QStackedWidget()
        self.home_page = HomePage(database, resource_dir)
        self.create_page = CreatePage(database)
        self.projects_page = ProjectsPage(database, paths)
        self.models_page = ModelsPage(database)
        self.audio_page = AudioPage(database, paths)
        self.settings_page = SettingsPage(database, resource_dir)
        self.about_page = AboutPage(database, resource_dir)

        self.pages = [
            self.home_page,
            self.create_page,
            self.projects_page,
            self.models_page,
            self.audio_page,
            self.settings_page,
            self.about_page,
        ]
        for page in self.pages:
            self.stack.addWidget(page)

        nav_items = [
            ("Início", "home", 0),
            ("Criar", "create", 1),
            ("Projetos", "projects", 2),
            ("Modelos", "models", 3),
            ("Áudios", "audio", 4),
            ("Configurações", "settings", 5),
            ("Sobre", "about", 6),
        ]
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[int, QPushButton] = {}
        for label, icon_name, index in nav_items:
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIcon(self._state_icon(icon_name))
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda checked=False, target=index: self.navigate(target))
            self.nav_group.addButton(button, index)
            self.nav_buttons[index] = button
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch(1)
        version_label = QLabel(f"AnkiiStudio · {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setObjectName("MutedLabel")
        sidebar_layout.addWidget(version_label)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)

        self.home_page.create_requested.connect(self.open_create)
        self.home_page.import_requested.connect(self.open_import)
        self.home_page.projects_requested.connect(lambda: self.navigate(2))
        self.create_page.project_created.connect(self.open_created_project)
        self.projects_page.changed.connect(self.refresh_related_pages)
        self.navigate(0)

    def _state_icon(self, icon_name: str) -> QIcon:
        icons = self.resource_dir / "icons"
        icon = QIcon()
        idle = icons / f"{icon_name}_idle.svg"
        active = icons / f"{icon_name}_active.svg"
        if idle.is_file():
            icon.addFile(str(idle), QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        if active.is_file():
            icon.addFile(str(active), QSize(), QIcon.Mode.Normal, QIcon.State.On)
        return icon

    def navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
        page = self.pages[index]
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()

    def open_create(self) -> None:
        self.create_page.set_creation_mode("import")
        self.navigate(1)

    def open_import(self) -> None:
        self.create_page.set_creation_mode("import")
        self.navigate(1)

    def open_created_project(self, project_id: int) -> None:
        self.projects_page.refresh(project_id)
        self.refresh_related_pages()
        self.navigate(2)

    def refresh_related_pages(self) -> None:
        self.home_page.refresh()
        self.models_page.refresh()
        self.audio_page.refresh()
        self.about_page.refresh()
