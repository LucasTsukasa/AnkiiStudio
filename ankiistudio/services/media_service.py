from __future__ import annotations

import json
from pathlib import Path

from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, MediaAsset, ProjectData, WikimediaMediaResult
from ankiistudio.services.image_service import ImageService
from ankiistudio.services.wikimedia_service import WikimediaService


class CardImageService:
    def __init__(
        self,
        database: Database,
        wikimedia: WikimediaService,
        image_service: ImageService,
    ) -> None:
        self.database = database
        self.wikimedia = wikimedia
        self.image_service = image_service

    @staticmethod
    def has_valid_image(card: FlashcardData) -> bool:
        if not card.image_path:
            return False
        path = Path(card.image_path)
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        # Imagens criadas antes da correção 0.10.0 podem conter exatamente o
        # artefato de alpha que vira um retângulo preto no Anki. Trate-as como
        # inválidas para que "Imagens para todos" possa regenerá-las.
        return not ImageService.is_alpha_mask_artifact(path)

    def apply_wikimedia_image(
        self,
        project: ProjectData,
        card: FlashcardData,
        result: WikimediaMediaResult,
    ) -> FlashcardData:
        if project.id is None or card.id is None:
            raise ValueError("Projeto e cartão devem estar salvos.")
        if not project.uses_images:
            raise ValueError("Este modelo não utiliza imagens.")
        # SVGs são vetoriais e o Pillow não os rasteriza diretamente. Para arquivos
        # do Commons usamos a miniatura rasterizada pelo próprio Wikimedia (Opção A),
        # preservando a qualidade do vetor sem adicionar um conversor SVG local.
        if result.mime == "image/svg+xml":
            if not result.thumbnail_url:
                raise RuntimeError("O Wikimedia não forneceu uma miniatura rasterizada para este SVG.")
            download_url = result.thumbnail_url
        else:
            download_url = result.file_url
        raw, _ = self.wikimedia.download(download_url)
        local_path = self.image_service.optimize(
            raw,
            result.title,
            flatten_transparency=result.mime == "image/svg+xml",
        )
        if not local_path.is_file() or local_path.stat().st_size <= 0:
            raise RuntimeError("A imagem foi baixada, mas o arquivo final não pôde ser validado.")
        card.image_path = str(local_path)
        self.database.update_card(card)
        self.database.add_media_asset(
            MediaAsset(
                project_id=project.id,
                card_id=card.id,
                kind="image",
                provider="wikimedia",
                local_path=str(local_path),
                source_title=result.title,
                source_url=result.description_url,
                author=result.author,
                license_name=result.license_name,
                license_url=result.license_url,
                modifications=(
                    "SVG rasterizado pelo Wikimedia, composto sobre fundo branco, redimensionado e convertido para WebP."
                    if result.mime == "image/svg+xml"
                    else "Redimensionamento e conversão para WebP."
                ),
                metadata_json=json.dumps(result.model_dump(), ensure_ascii=False),
            )
        )
        return card

    def apply_best_wikimedia_image(
        self,
        project: ProjectData,
        card: FlashcardData,
    ) -> FlashcardData:
        if not project.uses_images:
            raise ValueError("Este modelo não utiliza imagens.")
        if self.has_valid_image(card):
            return card

        # Caminho antigo/inválido não deve impedir nova busca.
        if card.image_path:
            card.image_path = ""
            self.database.update_card(card)

        # Pesquisa determinística: conteúdo original primeiro; tradução apenas como fallback.
        # Termos alternativos gerados por IA não participam da busca automática.
        terms: list[str] = []
        for candidate in (card.word, card.translation):
            candidate = candidate.strip()
            if candidate and candidate.casefold() not in {item.casefold() for item in terms}:
                terms.append(candidate)

        errors: list[str] = []
        for term in terms:
            try:
                results = self.wikimedia.search(term, kind="image", limit=8)
            except Exception as exc:
                errors.append(f"{term}: {exc}")
                continue
            for result in results:
                try:
                    return self.apply_wikimedia_image(project, card, result)
                except Exception as exc:
                    errors.append(f"{result.title}: {exc}")

        detail = f" Primeira falha: {errors[0]}" if errors else ""
        raise RuntimeError(f"Nenhuma imagem adequada foi encontrada para “{card.word}”.{detail}")
