from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from ankiistudio.config import AppPaths
from ankiistudio.constants import APP_NAME, APP_VERSION, ORGANIZATION_NAME
from ankiistudio.database import Database
from ankiistudio.ui.main_window import MainWindow
from ankiistudio.ui.theme import build_stylesheet


def configure_logging(paths: AppPaths) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(paths.logs_dir / "ankiistudio.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main() -> int:
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(APP_VERSION)
    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    try:
        paths = AppPaths()
        paths.ensure()
        configure_logging(paths)
        database = Database(paths.database_path)
        resource_dir = Path(__file__).resolve().parent / "resources"
        app.setStyleSheet(build_stylesheet(resource_dir, database.get_setting("appearance_theme", "dark")))
        window = MainWindow(database, paths, resource_dir)
        window.show()
        available = window.screen().availableGeometry()
        frame = window.frameGeometry()
        frame.moveCenter(available.center())
        window.move(frame.topLeft())
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Falha ao iniciar o AnkiiStudio",
            f"O aplicativo não pôde ser iniciado:\n\n{exc}",
        )
        logging.exception("Falha fatal durante a inicialização")
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
