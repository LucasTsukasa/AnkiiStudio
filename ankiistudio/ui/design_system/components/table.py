from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QTableView, QTableWidget, QWidget


class _ASTableMixin:
    def _configure_table(self) -> None:
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)


class ASTableView(_ASTableMixin, QTableView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ASTable")
        self._configure_table()


class ASTableWidget(_ASTableMixin, QTableWidget):
    def __init__(self, rows: int = 0, columns: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(rows, columns, parent)
        self.setObjectName("ASTable")
        self._configure_table()
