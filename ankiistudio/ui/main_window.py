from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QSize, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import AppPaths
from ankiistudio.constants import APP_NAME, APP_VERSION
from ankiistudio.database import Database
from ankiistudio.i18n import tr
from ankiistudio.services.update_service import DownloadedUpdate, UpdateInfo, UpdateService
from ankiistudio.ui.design_system.icons import IconRegistry
from ankiistudio.ui.design_system.components import ASButton, ASSidebar, ASSidebarItem, ASToastManager
from ankiistudio.ui.pages.home_page import HomePage
from ankiistudio.ui.workers import Worker


class MainWindow(QMainWindow):
    SIDEBAR_EXPANDED_WIDTH = 216
    SIDEBAR_COLLAPSED_WIDTH = 66
    DEFAULT_WIDTH = 1120
    DEFAULT_HEIGHT = 720
    SCREEN_MARGIN = 8
    WINDOW_GEOMETRY_SETTING = "main_window_geometry"

    def __init__(self, database: Database, paths: AppPaths, resource_dir: Path) -> None:
        super().__init__()
        self.database = database
        self.paths = paths
        self.resource_dir = resource_dir
        self.thread_pool = QThreadPool.globalInstance()
        self.update_service = UpdateService(paths)
        self.icons = IconRegistry(resource_dir)
        self._update_worker: Worker | None = None
        self._update_download_worker: Worker | None = None
        self._settings_dialog: Any | None = None
        self._sidebar_collapsed = database.get_setting("sidebar_collapsed", "0") == "1"
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(840, 560)
        self._geometry_restored = self._restore_window_geometry()
        if not self._geometry_restored:
            self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        icon_path = resource_dir / "icons" / "app.png"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        self.sidebar = ASSidebar()
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 14, 10, 12)
        sidebar_layout.setSpacing(4)

        self.brand_panel = QFrame()
        self.brand_panel.setObjectName("BrandPanel")
        brand_layout = QHBoxLayout(self.brand_panel)
        brand_layout.setContentsMargins(8, 8, 8, 12)
        brand_layout.setSpacing(9)
        self.brand_mark = QLabel()
        logo_path = resource_dir / "icons" / "app.png"
        if logo_path.is_file():
            self.brand_mark.setPixmap(QIcon(str(logo_path)).pixmap(QSize(24, 24)))
        self.brand_mark.setFixedSize(26, 26)
        self.brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_label = QLabel(APP_NAME)
        self.brand_label.setObjectName("Brand")
        brand_layout.addWidget(self.brand_mark)
        brand_layout.addWidget(self.brand_label)
        brand_layout.addStretch(1)
        sidebar_layout.addWidget(self.brand_panel)

        self.sidebar_toggle = ASButton("‹", variant="icon")
        self.sidebar_toggle.setObjectName("SidebarToggle")
        self.sidebar_toggle.setFixedSize(32, 32)
        self.sidebar_toggle.setToolTip("Recolher barra lateral")
        self.sidebar_toggle.setAccessibleName("Recolher barra lateral")
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        self.sidebar_toggle_row = QHBoxLayout()
        self.sidebar_toggle_row.setContentsMargins(0, 0, 0, 2)
        self.sidebar_toggle_row.addWidget(self.sidebar_toggle)
        sidebar_layout.addLayout(self.sidebar_toggle_row)

        self.stack = QStackedWidget()
        self.home_page = HomePage(database, resource_dir)
        self.pages: list[QWidget | None] = [self.home_page, None, None, None, None]
        self.stack.addWidget(self.home_page)
        for _index in range(1, len(self.pages)):
            placeholder = QWidget()
            placeholder.setObjectName(f"LazyPagePlaceholder{_index}")
            self.stack.addWidget(placeholder)

        nav_items = [
            ("Início", "home", 0),
            ("Criar", "create", 1),
            ("Projetos", "projects", 2),
            ("Roadmap", "roadmap", 3),
            ("Sobre", "about", 4),
        ]
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[int, ASSidebarItem] = {}
        self._nav_metadata: dict[QPushButton, tuple[str, str]] = {}
        for label, icon_name, index in nav_items:
            button = ASSidebarItem(label, icon=self.icons.icon(icon_name, stateful=True, size=18))
            button.clicked.connect(lambda _checked=False, target=index: self.navigate(target))
            self.nav_group.addButton(button, index)
            self.nav_buttons[index] = button
            self._nav_metadata[button] = (label, icon_name)
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch(1)
        self.settings_button = ASButton("Configurações", variant="ghost")
        self.settings_button.setProperty("asComponent", "sidebar-item")
        self.settings_button.setIcon(self.icons.icon("settings", stateful=True, size=18))
        self.settings_button.setIconSize(QSize(18, 18))
        self.settings_button.clicked.connect(self.open_settings)
        self._nav_metadata[self.settings_button] = ("Configurações", "settings")
        sidebar_layout.addWidget(self.settings_button)

        self.version_label = QLabel(f"{APP_NAME} · {APP_VERSION}")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setObjectName("MutedLabel")
        sidebar_layout.addWidget(self.version_label)

        root.addWidget(self.sidebar)
        root.addWidget(self.stack, 1)

        self.toasts = ASToastManager(central)
        self.toasts.setFixedWidth(330)
        self._position_toasts()

        self.home_page.create_requested.connect(self.open_create)
        self.home_page.import_requested.connect(self.open_import)
        self.home_page.projects_requested.connect(lambda: self.navigate(2))
        self._install_edit_actions()
        self._apply_sidebar_state(save=False)
        self.navigate(0, refresh=False)
        QTimer.singleShot(1500, self._check_updates_on_startup)

    def _ensure_page(self, index: int) -> QWidget:
        existing = self.pages[index]
        if existing is not None:
            return existing

        database = self.database
        paths = self.paths
        resource_dir = self.resource_dir
        if index == 1:
            from ankiistudio.ui.pages.create_page import CreatePage

            page = CreatePage(database, paths)
            page.project_created.connect(self.open_created_project)
        elif index == 2:
            from ankiistudio.ui.pages.projects_hub_page import ProjectsHubPage

            page = ProjectsHubPage(database, paths)
            page.changed.connect(self.refresh_related_pages)
        elif index == 3:
            from ankiistudio.ui.pages.roadmap_page import RoadmapPage

            page = RoadmapPage(paths, resource_dir)
        elif index == 4:
            from ankiistudio.ui.pages.about_page import AboutPage

            page = AboutPage(database, resource_dir)
        else:
            raise IndexError(f"Página inválida: {index}")

        placeholder = self.stack.widget(index)
        self.stack.removeWidget(placeholder)
        placeholder.deleteLater()
        self.stack.insertWidget(index, page)
        self.pages[index] = page
        return page

    def _loaded_page(self, index: int) -> QWidget | None:
        return self.pages[index]

    @property
    def create_page(self) -> QWidget:
        return self._ensure_page(1)

    @property
    def projects_page(self) -> QWidget:
        return self._ensure_page(2)

    @property
    def roadmap_page(self) -> QWidget:
        return self._ensure_page(3)

    @property
    def about_page(self) -> QWidget:
        return self._ensure_page(4)

    def _install_edit_actions(self) -> None:
        undo = QAction("Desfazer", self)
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        undo.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        undo.triggered.connect(lambda: self._invoke_focused_editor("undo"))
        self.addAction(undo)
        redo = QAction("Refazer", self)
        redo.setShortcuts([QKeySequence.StandardKey.Redo, QKeySequence("Ctrl+Shift+Z")])
        redo.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        redo.triggered.connect(lambda: self._invoke_focused_editor("redo"))
        self.addAction(redo)
        self.undo_action = undo
        self.redo_action = redo

    @staticmethod
    def _invoke_focused_editor(method_name: str) -> None:
        widget = QApplication.focusWidget()
        action = getattr(widget, method_name, None) if widget is not None else None
        if callable(action):
            action()

    def toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._apply_sidebar_state(save=True)

    def _apply_sidebar_state(self, *, save: bool) -> None:
        collapsed = self._sidebar_collapsed
        self.sidebar.setFixedWidth(self.SIDEBAR_COLLAPSED_WIDTH if collapsed else self.SIDEBAR_EXPANDED_WIDTH)
        self.brand_label.setVisible(not collapsed)
        self.version_label.setVisible(not collapsed)
        toggle_label = "Expandir barra lateral" if collapsed else "Recolher barra lateral"
        self.sidebar_toggle.setText("›" if collapsed else "‹")
        self.sidebar_toggle.setToolTip(toggle_label)
        self.sidebar_toggle.setAccessibleName(toggle_label)
        self.sidebar_toggle_row.setAlignment(
            self.sidebar_toggle,
            Qt.AlignmentFlag.AlignHCenter if collapsed else Qt.AlignmentFlag.AlignRight,
        )
        for button, (label, _icon) in self._nav_metadata.items():
            button.setText("" if collapsed else tr(label))
            button.setToolTip(tr(label) if collapsed else "")
            button.setStyleSheet("text-align:center;" if collapsed else "")
        if save:
            self.database.set_setting("sidebar_collapsed", "1" if collapsed else "0")

    def open_settings(self) -> None:
        from ankiistudio.ui.dialogs.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.database, self.paths, self.resource_dir, self)
        self._settings_dialog = dialog
        dialog.check_updates_requested.connect(lambda: self.check_for_updates(manual=True))
        dialog.ui_language_changed.connect(self._change_ui_language)
        dialog.exec()
        create_page = self._loaded_page(1)
        if create_page is not None:
            refresh_audio_options = getattr(create_page, "refresh_audio_options", None)
            if callable(refresh_audio_options):
                refresh_audio_options()
        projects_page = self._loaded_page(2)
        if projects_page is not None:
            refresh_project_audio = getattr(projects_page, "refresh_audio_profiles", None)
            if callable(refresh_project_audio):
                refresh_project_audio()
        self._settings_dialog = None

    def _settings_status(self, text: str, *, error: bool = False) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.status.show_message(text, error=error)

    def _change_ui_language(self, language: str) -> None:
        app = QApplication.instance()
        manager = getattr(app, "_ankiistudio_language_manager", None) if app is not None else None
        if manager is not None:
            manager.set_language(language)
        create_page = self._loaded_page(1)
        if create_page is not None:
            retranslate_create = getattr(create_page, "retranslate_ui", None)
            if callable(retranslate_create):
                retranslate_create()
        projects_page = self._loaded_page(2)
        if projects_page is not None:
            retranslate_projects = getattr(projects_page, "retranslate_ui", None)
            if callable(retranslate_projects):
                retranslate_projects()
        roadmap_page = self._loaded_page(3)
        if roadmap_page is not None:
            refresh_roadmap = getattr(roadmap_page, "refresh", None)
            if callable(refresh_roadmap):
                refresh_roadmap()
        self.undo_action.setText(tr("Desfazer"))
        self.redo_action.setText(tr("Refazer"))
        self._apply_sidebar_state(save=False)
        self._settings_status(tr("Idioma da interface atualizado."))

    def _check_updates_on_startup(self) -> None:
        if self.database.get_setting("check_updates", "1") == "1":
            self.check_for_updates(manual=False)

    def check_for_updates(self, *, manual: bool = False) -> None:
        if self._update_worker is not None:
            if manual:
                self._settings_status("Já existe uma verificação de atualização em andamento.")
            return
        if manual:
            self._settings_status("Procurando atualizações no GitHub...")
        worker = Worker(self.update_service.check, APP_VERSION)
        self._update_worker = worker
        worker.signals.result.connect(lambda result: self._handle_update_check(result, manual))
        worker.signals.error.connect(lambda message: self._handle_update_error(message, manual))
        worker.signals.finished.connect(lambda: setattr(self, "_update_worker", None))
        self.thread_pool.start(worker)

    def _handle_update_error(self, message: str, manual: bool) -> None:
        if manual:
            QMessageBox.warning(self, "Não foi possível verificar atualizações", message)
            self.toasts.show_toast(message, kind="error")
            self._settings_status(message, error=True)

    def _handle_update_check(self, result: object, manual: bool) -> None:
        if result is None:
            if manual:
                QMessageBox.information(
                    self,
                    "BenkyouStudio atualizado",
                    f"Você já está usando a versão mais recente disponível para este canal: {APP_VERSION}.",
                )
                self.toasts.show_toast("Você já está usando a versão mais recente.", kind="success")
                self._settings_status("Nenhuma atualização disponível.")
            return
        if not isinstance(result, UpdateInfo):
            return
        from ankiistudio.ui.dialogs.update_dialog import UpdateDialog

        update_parent = self._settings_dialog if self._settings_dialog is not None else self
        if UpdateDialog(result, update_parent).exec() != QDialog.DialogCode.Accepted:
            self._settings_status("Atualização adiada.")
            return
        projects_page = self._loaded_page(2)
        if projects_page is not None:
            resolve_pending = getattr(projects_page, "resolve_pending_changes", None)
            if callable(resolve_pending) and not resolve_pending("atualizar o aplicativo"):
                return
        self._download_update(result)

    def _download_update(self, info: UpdateInfo) -> None:
        if self._update_download_worker is not None:
            return
        self._settings_status(f"Baixando BenkyouStudio {info.version}...")
        worker = Worker(self.update_service.download, info)
        self._update_download_worker = worker
        worker.signals.result.connect(self._handle_downloaded_update)
        worker.signals.error.connect(lambda message: QMessageBox.critical(self, "Falha na atualização", message))
        worker.signals.finished.connect(lambda: setattr(self, "_update_download_worker", None))
        self.thread_pool.start(worker)

    def _handle_downloaded_update(self, result: object) -> None:
        if not isinstance(result, DownloadedUpdate):
            return
        if not self.update_service.can_self_update():
            QMessageBox.information(
                self,
                "Atualização baixada",
                f"O pacote {result.info.version} foi baixado em:\n{result.archive_path}\n\n"
                "A instalação automática é aplicada quando o BenkyouStudio está executando pela versão portátil do Windows.",
            )
            self._settings_status("Atualização baixada.")
            return
        try:
            self.update_service.schedule_install_and_restart(result)
        except Exception as exc:
            QMessageBox.critical(self, "Falha na atualização", str(exc))
            return
        QMessageBox.information(
            self,
            "Atualização pronta",
            "O BenkyouStudio será fechado, atualizado e aberto novamente automaticamente.",
        )
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _restore_window_geometry(self) -> bool:
        encoded = self.database.get_setting(self.WINDOW_GEOMETRY_SETTING, "").strip()
        if not encoded:
            return False
        try:
            geometry = QByteArray.fromBase64(encoded.encode("ascii"))
            return not geometry.isEmpty() and self.restoreGeometry(geometry)
        except (UnicodeEncodeError, ValueError):
            return False

    def _save_window_geometry(self) -> None:
        encoded = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.database.set_setting(self.WINDOW_GEOMETRY_SETTING, encoded)

    @property
    def geometry_restored(self) -> bool:
        return self._geometry_restored

    def ensure_visible_on_screen(self, *, center: bool = False) -> None:
        """Mantém o frame completo dentro da área útil de um monitor conectado."""
        frame = self.frameGeometry()
        screen = QApplication.screenAt(frame.center()) or self.screen() or QApplication.primaryScreen()
        if screen is None or self.isMaximized() or self.isFullScreen():
            return

        available = screen.availableGeometry().adjusted(
            self.SCREEN_MARGIN,
            self.SCREEN_MARGIN,
            -self.SCREEN_MARGIN,
            -self.SCREEN_MARGIN,
        )
        if available.width() <= 0 or available.height() <= 0:
            return

        overflow_width = max(0, frame.width() - available.width())
        overflow_height = max(0, frame.height() - available.height())
        if overflow_width or overflow_height:
            self.resize(
                max(self.minimumWidth(), self.width() - overflow_width),
                max(self.minimumHeight(), self.height() - overflow_height),
            )
            frame = self.frameGeometry()

        frame_offset_x = frame.x() - self.x()
        frame_offset_y = frame.y() - self.y()
        if center:
            centered_frame = frame
            centered_frame.moveCenter(available.center())
            target_x = centered_frame.x()
            target_y = centered_frame.y()
        else:
            target_x = min(max(frame.x(), available.left()), available.right() - frame.width() + 1)
            target_y = min(max(frame.y(), available.top()), available.bottom() - frame.height() + 1)

        max_x = max(available.left(), available.right() - frame.width() + 1)
        max_y = max(available.top(), available.bottom() - frame.height() + 1)
        target_x = min(max(target_x, available.left()), max_x)
        target_y = min(max(target_y, available.top()), max_y)
        self.move(target_x - frame_offset_x, target_y - frame_offset_y)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        projects_page = self._loaded_page(2)
        confirm_close = getattr(projects_page, "confirm_close", None) if projects_page is not None else None
        if not callable(confirm_close) or confirm_close():
            self._save_window_geometry()
            event.accept()
        else:
            event.ignore()

    def _state_icon(self, icon_name: str) -> QIcon:
        return self.icons.icon(icon_name, stateful=True, size=18)

    def _position_toasts(self) -> None:
        if not hasattr(self, "toasts"):
            return
        central = self.centralWidget()
        if central is None:
            return
        margin = 18
        width = min(330, max(240, central.width() - margin * 2))
        self.toasts.setFixedWidth(width)
        self.toasts.adjustSize()
        self.toasts.move(max(margin, central.width() - width - margin), margin)
        self.toasts.raise_()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_toasts()

    def navigate(self, index: int, *, refresh: bool = True) -> None:
        page = self._ensure_page(index)
        self.stack.setCurrentWidget(page)
        self.nav_buttons[index].setChecked(True)
        refresh_page = getattr(page, "refresh", None)
        if refresh and callable(refresh_page):
            refresh_page()

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
        self.projects_page.open_project(project_id)

    def refresh_related_pages(self) -> None:
        self.home_page.refresh()
        for index in (2, 4):
            page = self._loaded_page(index)
            if page is None:
                continue
            refresh = getattr(page, "refresh", None)
            if callable(refresh):
                refresh()
