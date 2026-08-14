from __future__ import annotations

from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
)

from ankiistudio.constants import APP_VERSION
from ankiistudio.services.update_service import UpdateInfo
from ankiistudio.ui.design_system.components import ASButton, ASDialog


class UpdateDialog(ASDialog):
    def __init__(self, info: UpdateInfo, parent=None) -> None:
        super().__init__(parent, dialog_role="update")
        self.setObjectName("UpdateDialog")
        self.setWindowTitle("Nova versão disponível")
        self.resize(620, 470)
        self.setMinimumSize(520, 400)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)

        title = QLabel("✨ Nova versão disponível")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        channel = "Pré-lançamento" if info.prerelease else "Versão estável"
        badge = QLabel(channel.upper())
        badge.setObjectName("Badge")
        root.addWidget(badge)

        versions = QHBoxLayout()
        installed = QLabel(f"Sua versão\n{APP_VERSION}")
        available = QLabel(f"Disponível\n{info.version}")
        installed.setObjectName("SectionSubtitle")
        available.setObjectName("SectionTitle")
        versions.addWidget(installed, 1)
        versions.addWidget(available, 1)
        root.addLayout(versions)

        notes_title = QLabel("Novidades")
        notes_title.setObjectName("SectionTitle")
        root.addWidget(notes_title)
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setPlainText(info.notes.strip() or "Esta versão inclui melhorias e correções do AnkiiStudio.")
        root.addWidget(notes, 1)

        buttons = QDialogButtonBox()
        later = ASButton("Agora não", variant="ghost")
        update = ASButton("Baixar atualização", variant="primary")
        update.setObjectName("PrimaryButton")
        later.clicked.connect(self.reject)
        update.clicked.connect(self.accept)
        buttons.addButton(later, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.addButton(update, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)
