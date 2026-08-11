from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, ImageSearchResult, MediaAsset, ProjectData
from ankiistudio.services.image_service import ImageService

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


class CardImageService:
    def __init__(
        self,
        database: Database,
        search_service,
        image_service: ImageService,
    ) -> None:
        self.database = database
        # search_service pode ser ImageSearchService ou WikimediaService/Fake nos testes antigos.
        self.search_service = search_service
        self.wikimedia = search_service
        self.image_service = image_service

    @staticmethod
    def has_valid_image(card: FlashcardData) -> bool:
        if not card.image_path:
            return False
        path = Path(card.image_path)
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        return not ImageService.is_alpha_mask_artifact(path)

    @staticmethod
    def manual_search_terms(card: FlashcardData) -> tuple[str, list[str]]:
        """Retorna busca principal e sugestões para a pesquisa manual de um cartão.

        Na pesquisa manual o conteúdo original é sempre a consulta principal. Os
        demais campos do cartão aparecem apenas como sugestões auxiliares. Isso
        evita substituir caracteres como あ pela tradução "A" sem impedir que o
        usuário explore traduções, leitura, romanização e termos visuais.
        """
        primary = str(card.word or "").strip()
        auxiliary: list[str] = []
        seen = {unicodedata.normalize("NFKC", primary).casefold()} if primary else set()
        for candidate in [
            card.translation,
            card.romanization,
            card.reading,
            *card.image_search_terms,
        ]:
            text = str(candidate or "").strip()
            key = unicodedata.normalize("NFKC", text).casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            auxiliary.append(text)
        return primary, auxiliary

    @staticmethod
    def preferred_search_terms(card: FlashcardData) -> list[str]:
        """Retorna a ordem de consultas usada pela busca automática/em lote.

        Quando o cartão possui `image_search_terms`, esses termos visuais explícitos
        continuam tendo prioridade, pois foram criados justamente para representar
        conceitos concretos/abstratos de forma pesquisável. Quando a lista está vazia,
        o conteúdo principal original vem primeiro. Essa regra é importante para kana,
        letras e símbolos isolados: `お` deve ser pesquisado como `お`, e não como a
        tradução `O`. A tradução permanece como fallback caso a consulta principal não
        produza uma imagem utilizável.
        """
        ordered: list[str] = []
        seen: set[str] = set()
        candidates = (
            [*card.image_search_terms, card.translation, card.word]
            if card.image_search_terms
            else [card.word, card.translation]
        )
        for candidate in candidates:
            text = str(candidate or "").strip()
            key = unicodedata.normalize("NFKC", text).casefold()
            if text and key not in seen:
                seen.add(key)
                ordered.append(text)
        return ordered

    def apply_search_result(
        self,
        project: ProjectData,
        card: FlashcardData,
        result: ImageSearchResult,
    ) -> FlashcardData:
        if project.id is None or card.id is None:
            raise ValueError("Projeto e cartão devem estar salvos.")
        if not project.card_uses_component(card, "image"):
            raise ValueError("A estrutura deste cartão não utiliza imagens.")

        is_wikimedia_svg = result.provider == "wikimedia" and result.mime == "image/svg+xml"
        if is_wikimedia_svg:
            if not result.thumbnail_url:
                raise RuntimeError("O Wikimedia não forneceu uma miniatura rasterizada para este SVG.")
            download_url = result.thumbnail_url
        else:
            download_url = result.file_url or result.thumbnail_url
        if not download_url:
            raise RuntimeError("A fonte não forneceu uma URL utilizável para a imagem.")

        raw, _ = self.search_service.download(download_url)
        local_path = self.image_service.optimize(
            raw,
            result.title,
            flatten_transparency=is_wikimedia_svg,
        )
        if not local_path.is_file() or local_path.stat().st_size <= 0:
            raise RuntimeError("A imagem foi baixada, mas o arquivo final não pôde ser validado.")

        card.image_path = str(local_path)
        self.database.update_card(card)
        self.database.delete_media_assets_for_card(card.id, "image")
        self.database.add_media_asset(
            MediaAsset(
                project_id=project.id,
                card_id=card.id,
                kind="image",
                provider=result.provider or "unknown",
                local_path=str(local_path),
                source_title=result.title,
                source_url=result.description_url,
                author=result.author,
                license_name=result.license_name,
                license_url=result.license_url,
                modifications=(
                    "SVG rasterizado pelo Wikimedia, composto sobre fundo branco, redimensionado e convertido para WebP."
                    if is_wikimedia_svg
                    else "Redimensionamento e conversão para WebP."
                ),
                metadata_json=json.dumps(result.model_dump(), ensure_ascii=False),
            )
        )
        return card

    # Compatibilidade com chamadas existentes.
    def apply_wikimedia_image(
        self, project: ProjectData, card: FlashcardData, result: ImageSearchResult
    ) -> FlashcardData:
        if not result.provider:
            result.provider = "wikimedia"
        return self.apply_search_result(project, card, result)

    @staticmethod
    def _wikimedia_result_matches_non_latin_term(result: ImageSearchResult, term: str) -> bool:
        # Para buscas não latinas, evita aceitar automaticamente um arquivo cuja página
        # apareceu apenas por metadados distantes do conceito. Para um caractere kana
        # isolado, também aceita o nome Unicode equivalente usado nos títulos do Commons
        # (ex.: お -> "Hiragana letter O").
        if result.provider != "wikimedia":
            return True
        normalized_term = unicodedata.normalize("NFKC", term).casefold().strip()
        if not normalized_term or all(ord(ch) < 128 for ch in normalized_term):
            return True
        haystack = unicodedata.normalize(
            "NFKC",
            " ".join((result.title, result.description, result.credit)),
        ).casefold()
        if normalized_term in haystack:
            return True

        if len(normalized_term) == 1:
            unicode_name = unicodedata.name(normalized_term, "").casefold()
            if unicode_name.startswith(("hiragana ", "katakana ")):
                name_parts = unicode_name.split()
                script = name_parts[0]
                pronunciation = name_parts[-1] if name_parts else ""
                punctuation = str.maketrans({char: " " for char in "_-.:,;()[]{}"})
                haystack_words = set(haystack.translate(punctuation).replace("/", " ").split())
                if script in haystack_words and pronunciation in haystack_words:
                    return True
        return False

    def apply_best_image(self, project: ProjectData, card: FlashcardData) -> FlashcardData:
        if not project.card_uses_component(card, "image"):
            raise ValueError("A estrutura deste cartão não utiliza imagens.")
        if self.has_valid_image(card):
            return card

        if card.image_path:
            card.image_path = ""
            self.database.update_card(card)

        errors: list[str] = []
        for term in self.preferred_search_terms(card):
            try:
                if hasattr(self.search_service, "search_provider_ordered"):
                    results = self.search_service.search_provider_ordered(term, limit_per_provider=8)
                else:
                    results = self.search_service.search(term, kind="image", limit=8)
            except Exception as exc:
                errors.append(f"{term}: {exc}")
                continue
            for result in results:
                if not self._wikimedia_result_matches_non_latin_term(result, term):
                    continue
                try:
                    return self.apply_search_result(project, card, result)
                except Exception as exc:
                    errors.append(f"{result.title}: {exc}")

        detail = f" Primeira falha: {errors[0]}" if errors else ""
        raise RuntimeError(f"Nenhuma imagem adequada foi encontrada para “{card.word}”.{detail}")

    def apply_best_wikimedia_image(self, project: ProjectData, card: FlashcardData) -> FlashcardData:
        return self.apply_best_image(project, card)

    def import_image_file(
        self, project: ProjectData, card: FlashcardData, source: Path
    ) -> FlashcardData:
        if project.id is None or card.id is None:
            raise ValueError("Projeto e cartão devem estar salvos.")
        if not project.card_uses_component(card, "image"):
            raise ValueError("A estrutura deste cartão não utiliza imagens.")
        source = source.expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError("O arquivo de imagem selecionado não existe.")
        if source.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError("Formato de imagem não suportado para importação.")
        raw = source.read_bytes()
        if not raw:
            raise ValueError("O arquivo de imagem está vazio.")
        local_path = self.image_service.optimize(raw, source.name, flatten_transparency=True)
        card.image_path = str(local_path)
        self.database.update_card(card)
        self.database.delete_media_assets_for_card(card.id, "image")
        self.database.add_media_asset(
            MediaAsset(
                project_id=project.id,
                card_id=card.id,
                kind="image",
                provider="user_import",
                local_path=str(local_path),
                source_title=source.name,
                modifications="Imagem importada pelo usuário, redimensionada e convertida para WebP.",
                metadata_json=json.dumps(
                    {"original_filename": source.name, "imported": True},
                    ensure_ascii=False,
                ),
            )
        )
        return card

    def remove_image(self, card: FlashcardData) -> FlashcardData:
        if card.id is None:
            raise ValueError("Cartão sem identificador.")
        previous = card.image_path
        card.image_path = ""
        self.database.update_card(card)
        self.database.delete_media_assets_for_card(card.id, "image")
        self._delete_unreferenced_file(previous, "image")
        return card

    def _delete_unreferenced_file(self, raw_path: str, kind: str) -> None:
        if not raw_path or self.database.count_card_media_path_references(raw_path, kind) > 0:
            return
        path = Path(raw_path)
        try:
            if path.is_file() and path.resolve().parent == self.image_service.images_dir.resolve():
                path.unlink()
        except OSError:
            pass
