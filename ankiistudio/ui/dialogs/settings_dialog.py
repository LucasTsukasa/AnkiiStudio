from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout

from ankiistudio.config import AppPaths
from ankiistudio.database import Database
from ankiistudio.ui.pages.settings_page import SettingsPage
from ankiistudio.ui.design_system.components import ASDialog


class SettingsDialog(ASDialog):
    check_updates_requested = Signal()
    ui_language_changed = Signal(str)

    def __init__(self, database: Database, paths: AppPaths, resource_dir: Path, parent=None) -> None:
        super().__init__(parent, dialog_role="settings")
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("Configurações")
        self.setModal(True)
        self.resize(900, 650)
        self.setMinimumSize(720, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.page = SettingsPage(database, paths, resource_dir)
        self.page.check_updates_requested.connect(self.check_updates_requested.emit)
        self.page.ui_language_changed.connect(self.ui_language_changed.emit)
        layout.addWidget(self.page)

    @property
    def status(self):
        return self.page.status
