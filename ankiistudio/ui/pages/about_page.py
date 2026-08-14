from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ankiistudio.constants import APP_NAME, APP_VERSION, GITHUB_URL
from ankiistudio.database import Database
from ankiistudio.i18n import tr
from ankiistudio.ui.design_system.components import ASButton, ASCard
from ankiistudio.ui.widgets import PageHeader, PageScrollArea, SectionCard


class AboutPage(QWidget):
    def __init__(self, database: Database, resource_dir: Path) -> None:
        super().__init__()
        self.database = database
        self.resource_dir = resource_dir

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "Sobre",
                "Informações do projeto, autoria, licença e uso de serviços externos.",
            )
        )

        hero = ASCard(variant="raised")
        hero.setObjectName("HeroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        hero_layout.setSpacing(18)
        app_icon = QLabel()
        icon_path = resource_dir / "icons" / "app.png"
        if icon_path.is_file():
            app_icon.setPixmap(QIcon(str(icon_path)).pixmap(QSize(72, 72)))
        app_icon.setFixedSize(78, 78)
        app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_layout = QVBoxLayout()
        name = QLabel(APP_NAME)
        name.setObjectName("HeroName")
        subtitle = QLabel(
            "Aplicativo desktop para criação, organização e exportação de flashcards compatíveis com o Anki."
        )
        subtitle.setObjectName("SectionSubtitle")
        subtitle.setWordWrap(True)
        text_layout.addWidget(name)
        text_layout.addWidget(subtitle)
        hero_layout.addWidget(app_icon)
        hero_layout.addLayout(text_layout, 1)
        version = QLabel(f"Versão {APP_VERSION}")
        version.setObjectName("Badge")
        hero_layout.addWidget(version, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(hero)

        developer = SectionCard(
            "Desenvolvedor",
            "Repositório, histórico de versões e código-fonte do projeto.",
        )
        dev_row = QHBoxLayout()
        github_icon = QLabel()
        github_path = resource_dir / "icons" / "github.svg"
        if github_path.is_file():
            github_icon.setPixmap(QIcon(str(github_path)).pixmap(QSize(32, 32)))
        github_icon.setFixedSize(36, 36)
        dev_text = QVBoxLayout()
        author = QLabel("Lucas Tsukasa")
        author.setObjectName("DeveloperName")
        handle = QLabel("github.com/LucasTsukasa")
        handle.setObjectName("MutedLabel")
        dev_text.addWidget(author)
        dev_text.addWidget(handle)
        github_button = ASButton("Abrir GitHub")
        github_button.setObjectName("PrimaryButton")
        if github_path.is_file():
            github_button.setIcon(QIcon(str(github_path)))
            github_button.setIconSize(QSize(17, 17))
        github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        dev_row.addWidget(github_icon)
        dev_row.addLayout(dev_text, 1)
        dev_row.addWidget(github_button)
        developer.root.addLayout(dev_row)
        layout.addWidget(developer)

        purpose = SectionCard("Sobre o aplicativo")
        purpose_text = QLabel(
            "O AnkiiStudio permite criar projetos em um amplo catálogo de idiomas. "
            "Modelos padrão revisados estão disponíveis para japonês; os demais idiomas utilizam "
            "o modelo Personalizado nesta versão. Integrações externas são acionadas somente quando configuradas e utilizadas pelo usuário."
        )
        purpose_text.setWordWrap(True)
        purpose_text.setObjectName("SectionSubtitle")
        purpose.root.addWidget(purpose_text)
        languages = QLabel("Idiomas: catálogo ISO amplo · modelos padrão atuais em Japonês")
        languages.setObjectName("Badge")
        purpose.root.addWidget(languages, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(purpose)

        license_card = SectionCard("Licença")
        license_text = QLabel(
            "O código-fonte do AnkiiStudio é distribuído sob a GNU General Public License v3.0 (GPL-3.0). "
            "Dependências e serviços de terceiros permanecem sujeitos às respectivas licenças e termos de uso."
        )
        license_text.setWordWrap(True)
        license_text.setObjectName("SectionSubtitle")
        license_card.root.addWidget(license_text)
        layout.addWidget(license_card)

        media = SectionCard("Conteúdo e mídias de terceiros")
        warning = QLabel(
            "Imagens e áudios podem ser obtidos de serviços externos, como o Wikimedia Commons. "
            "Autoria, direitos e condições de reutilização permanecem vinculados à fonte e à licença de cada mídia. "
            "Os metadados disponíveis são preservados internamente pelo AnkiiStudio."
        )
        warning.setWordWrap(True)
        warning.setObjectName("SectionSubtitle")
        self.media_count = QLabel()
        self.media_count.setObjectName("Badge")
        media.root.addWidget(warning)
        media.root.addWidget(self.media_count, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(media)

        layout.addStretch(1)
        root.addWidget(PageScrollArea(content))
        self.refresh()

    def refresh(self) -> None:
        self.media_count.setText(
            tr(f"{self.database.count_media_assets()} mídias registradas localmente")
        )
