from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThreadPool, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import AppPaths
from ankiistudio.i18n import tr
from ankiistudio.services.roadmap_service import RoadmapService
from ankiistudio.ui.design_system.components import ASCard
from ankiistudio.ui.widgets import PageHeader, PageScrollArea, SectionCard
from ankiistudio.ui.workers import Worker


_STATUS_LABELS = {
    "completed": "✓ CONCLUÍDO",
    "in_progress": "◉ EM DESENVOLVIMENTO",
    "planned": "◇ PLANEJADO",
}


class RoadmapTimeline(QWidget):
    BREAKPOINT = 760

    def __init__(self) -> None:
        super().__init__()
        self._items: list[dict[str, Any]] = []
        self._compact: bool | None = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(0)

    def set_items(self, items: list[dict[str, Any]]) -> None:
        self._items = list(items)
        self._compact = self.width() < self.BREAKPOINT
        self._rebuild()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        compact = self.width() < self.BREAKPOINT
        if self._compact is not None and compact != self._compact:
            self._compact = compact
            QTimer.singleShot(0, self._rebuild)
        super().resizeEvent(event)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild(self) -> None:
        self._clear()
        if not self._items:
            empty = SectionCard(
                "Roadmap indisponível",
                "Não foi possível carregar o planejamento desta versão.",
            )
            self._layout.addWidget(empty)
            return

        compact = bool(self._compact)
        for index, item in enumerate(self._items):
            row = QWidget()
            row.setObjectName("RoadmapRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12 if compact else 18)

            marker = self._marker(item, index)
            card = self._card(item)
            if compact:
                row_layout.addWidget(marker)
                row_layout.addWidget(card, 1)
            else:
                spacer_left = QWidget()
                spacer_right = QWidget()
                spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                if index % 2 == 0:
                    row_layout.addWidget(card, 1)
                    row_layout.addWidget(marker)
                    row_layout.addWidget(spacer_right, 1)
                else:
                    row_layout.addWidget(spacer_left, 1)
                    row_layout.addWidget(marker)
                    row_layout.addWidget(card, 1)
            self._layout.addWidget(row)
        self._layout.addStretch(1)

    def _marker(self, item: dict[str, Any], index: int) -> QWidget:
        status = str(item.get("status") or "planned")
        marker = QWidget()
        marker.setFixedWidth(34)
        layout = QVBoxLayout(marker)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top = QFrame()
        top.setObjectName("RoadmapLine")
        top.setFixedWidth(2)
        top.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        if index == 0:
            top.setStyleSheet("background: transparent; border: 0;")
        layout.addWidget(top, 1, Qt.AlignmentFlag.AlignHCenter)

        node = QLabel("●")
        node.setObjectName(
            {
                "completed": "RoadmapNodeCompleted",
                "in_progress": "RoadmapNodeInProgress",
                "planned": "RoadmapNodePlanned",
            }.get(status, "RoadmapNodePlanned")
        )
        node.setAlignment(Qt.AlignmentFlag.AlignCenter)
        node.setFixedSize(34, 34)
        layout.addWidget(node, 0, Qt.AlignmentFlag.AlignHCenter)

        bottom = QFrame()
        bottom.setObjectName("RoadmapLine")
        bottom.setFixedWidth(2)
        bottom.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        if index == len(self._items) - 1:
            bottom.setStyleSheet("background: transparent; border: 0;")
        layout.addWidget(bottom, 1, Qt.AlignmentFlag.AlignHCenter)
        return marker

    def _card(self, item: dict[str, Any]) -> QFrame:
        status = str(item.get("status") or "planned")
        card = ASCard()
        card.setObjectName("RoadmapCardCurrent" if item.get("current") else "RoadmapCard")
        card.setMinimumWidth(260)
        card.setMaximumWidth(520)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        heading = QHBoxLayout()
        title = QLabel(str(item.get("title") or ""))
        title._i18n_skip = True
        title.setObjectName("RoadmapTitle")
        title.setWordWrap(True)
        status_label = QLabel(tr(_STATUS_LABELS.get(status, "◇ PLANEJADO")))
        status_label.setObjectName(
            {
                "completed": "RoadmapStatusCompleted",
                "in_progress": "RoadmapStatusInProgress",
                "planned": "RoadmapStatusPlanned",
            }.get(status, "RoadmapStatusPlanned")
        )
        heading.addWidget(title, 1)
        heading.addWidget(status_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)

        if item.get("current"):
            current = QLabel(tr("VERSÃO ATUAL"))
            current.setObjectName("RoadmapCurrentBadge")
            layout.addWidget(current, 0, Qt.AlignmentFlag.AlignLeft)

        description_text = str(item.get("description") or "")
        if description_text:
            description = QLabel(description_text)
            description._i18n_skip = True
            description.setObjectName("RoadmapDescription")
            description.setWordWrap(True)
            layout.addWidget(description)

        details = [str(value) for value in (item.get("details") or []) if str(value).strip()]
        if details:
            details_label = QLabel("\n".join(f"• {detail}" for detail in details))
            details_label._i18n_skip = True
            details_label.setObjectName("RoadmapDetails")
            details_label.setWordWrap(True)
            layout.addWidget(details_label)
        return card


class RoadmapPage(QWidget):
    def __init__(self, paths: AppPaths, resource_dir) -> None:
        super().__init__()
        self.paths = paths
        self.service = RoadmapService(
            resource_dir / "roadmap.json",
            paths.cache_dir / "roadmap.json",
        )
        self.thread_pool = QThreadPool.globalInstance()
        self._worker: Worker | None = None
        self._remote_checked = False
        self._payload: dict[str, Any] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "Roadmap",
                "Acompanhe a evolução do BenkyouStudio e os próximos recursos planejados.",
            )
        )

        note = SectionCard()
        note_label = QLabel(
            "O planejamento pode mudar durante o desenvolvimento. Itens planejados não representam uma data de lançamento garantida."
        )
        note_label.setObjectName("SectionSubtitle")
        note_label.setWordWrap(True)
        note.root.addWidget(note_label)
        layout.addWidget(note)

        self.timeline = RoadmapTimeline()
        layout.addWidget(self.timeline)

        self.updated_label = QLabel()
        self.updated_label.setObjectName("MutedLabel")
        self.updated_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.updated_label)
        layout.addStretch(1)
        root.addWidget(PageScrollArea(content))
        self._payload = self.service.load_available()
        self._render_payload(self._payload)

    def refresh(self) -> None:
        self._payload = self.service.load_available()
        self._render_payload(self._payload)
        if self._worker is None and not self._remote_checked:
            self._fetch_remote()

    def _render_payload(self, payload: dict[str, Any]) -> None:
        self.timeline.set_items(list(payload.get("items") or []))
        updated_at = str(payload.get("updated_at") or "").strip()
        self.updated_label.setText(
            f"{tr('Roadmap atualizado em')} {updated_at}." if updated_at else ""
        )

    def _fetch_remote(self) -> None:
        self._remote_checked = True
        worker = Worker(self.service.fetch_remote)
        self._worker = worker
        worker.signals.result.connect(self._remote_loaded)
        # O Roadmap é informativo: falhas de rede usam silenciosamente o cache/local.
        worker.signals.error.connect(lambda _message: None)

        def finished() -> None:
            self._worker = None

        worker.signals.finished.connect(finished)
        self.thread_pool.start(worker)

    def _remote_loaded(self, result: object) -> None:
        if not isinstance(result, dict):
            return
        self._payload = result
        self._render_payload(result)
