from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import httpx

from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, ImageSearchResult, MediaAsset, ProjectData
from ankiistudio.services.image_service import ImageService
from ankiistudio.services.image_sources import ImageSearchService

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
    @lru_cache(maxsize=2048)
    def _is_alpha_mask_artifact_cached(path_text: str, mtime_ns: int, size: int) -> bool:
        del mtime_ns, size  # fazem parte da chave e invalidam o cache quando o arquivo muda
        return ImageService.is_alpha_mask_artifact(Path(path_text))

    @classmethod
    def has_valid_image(cls, card: FlashcardData) -> bool:
        if not card.image_path:
            return False
        path = Path(card.image_path)
        if not path.is_file():
            return False
        try:
            stat = path.stat()
        except OSError:
            return False
        if stat.st_size <= 0:
            return False
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        return not cls._is_alpha_mask_artifact_cached(resolved, stat.st_mtime_ns, stat.st_size)

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

        O conteúdo principal original vem primeiro, reproduzindo a consulta que o
        usuário vê na pesquisa manual. Termos visuais explícitos gerados/importados
        entram em seguida e a tradução permanece como fallback. Para kana, letras e
        símbolos isolados isso preserva a busca pelo próprio caractere.
        """
        ordered: list[str] = []
        seen: set[str] = set()
        candidates = [card.word, *card.image_search_terms, card.translation]
        for candidate in candidates:
            text = str(candidate or "").strip()
            key = unicodedata.normalize("NFKC", text).casefold()
            if text and key not in seen:
                seen.add(key)
                ordered.append(text)
        return ordered

    @staticmethod
    def _normalize_match_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return " ".join(re.sub(r"[^\w]+", " ", without_marks.casefold(), flags=re.UNICODE).split())

    @staticmethod
    def _canonical_match_token(token: str) -> str:
        """Normalização leve para plurais ingleses comuns sem tentar fazer NLP."""
        if len(token) > 4 and token.endswith("ies"):
            return token[:-3] + "y"
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            return token[:-1]
        return token

    @classmethod
    def _match_tokens(cls, value: str) -> list[str]:
        return [
            cls._canonical_match_token(token)
            for token in cls._normalize_match_text(value).split()
            if token
        ]

    @classmethod
    def _term_metadata_score(cls, result: ImageSearchResult, term: str) -> int:
        """Pontua quanto os metadados do resultado representam um termo visual.

        A pontuação usa apenas título/descrição fornecidos pela fonte. Ela não tenta
        inferir o conteúdo dos pixels e, por isso, é conservadora: correspondência
        completa recebe nota alta; correspondência parcial de termos compostos não
        basta para a seleção automática.
        """
        wanted = cls._match_tokens(term)
        if not wanted:
            return 0

        title_tokens = set(cls._match_tokens(result.title))
        description_tokens = set(cls._match_tokens(result.description))

        def coverage(tokens: set[str]) -> float:
            if not tokens:
                return 0.0
            matched = sum(1 for token in wanted if token in tokens)
            return matched / len(wanted)

        title_coverage = coverage(title_tokens)
        description_coverage = coverage(description_tokens)
        if title_coverage >= 1.0:
            return 120
        if description_coverage >= 1.0:
            return 95
        best = max(title_coverage, description_coverage)
        if best >= 0.75:
            return 70
        if best >= 0.50:
            return 35
        if best > 0:
            return 15
        return 0

    @classmethod
    def _result_relevance_score(
        cls,
        card: FlashcardData,
        result: ImageSearchResult,
        searched_term: str,
    ) -> int:
        """Retorna a relevância textual usada somente na seleção automática.

        Quando há `image_search_terms`, eles funcionam como a evidência principal de
        relevância. Isso impede que o primeiro resultado semanticamente distante de
        uma busca ampla seja aceito apenas porque a fonte o retornou. Sem termos
        visuais explícitos, preservamos o comportamento histórico (incluindo a regra
        especial de kana) para não regredir cartões antigos/modelos internos.
        """
        if not card.image_search_terms:
            return 100 if cls._wikimedia_result_matches_non_latin_term(result, searched_term) else 0

        visual_score = max(
            (cls._term_metadata_score(result, term) for term in card.image_search_terms),
            default=0,
        )
        if visual_score:
            return visual_score

        # Um título/descrição que contém literalmente o conteúdo original não deve ser
        # descartado só porque os termos auxiliares vieram em outro idioma.
        original_score = cls._term_metadata_score(result, card.word)
        if original_score >= 95:
            return original_score

        # A consulta em andamento e a tradução servem apenas como evidência fraca
        # quando existem termos visuais explícitos; sozinhas não ultrapassam o limiar.
        return max(
            min(cls._term_metadata_score(result, searched_term), 55),
            min(cls._term_metadata_score(result, card.translation), 50),
        )

    @classmethod
    def _rank_relevant_results(
        cls,
        card: FlashcardData,
        searched_term: str,
        results: list[ImageSearchResult],
    ) -> list[ImageSearchResult]:
        minimum_score = 60 if card.image_search_terms else 1
        ranked: list[tuple[int, int, ImageSearchResult]] = []
        for index, result in enumerate(results):
            if not cls._wikimedia_result_matches_non_latin_term(result, searched_term):
                # Quando há termos visuais explícitos, um resultado Wikimedia pode ter
                # título em outro idioma e ainda ser válido; nesse caso a pontuação
                # desses termos é a autoridade.
                if not card.image_search_terms:
                    continue
            score = cls._result_relevance_score(card, result, searched_term)
            if score >= minimum_score:
                ranked.append((score, index, result))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [result for _score, _index, result in ranked]

    def apply_search_result(
        self,
        project: ProjectData,
        card: FlashcardData,
        result: ImageSearchResult,
        *,
        http_client: httpx.Client | None = None,
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

        if isinstance(self.search_service, ImageSearchService):
            raw, _ = self.search_service.download(download_url, client=http_client)
        else:
            raw, _ = self.search_service.download(download_url)
        local_path = self.image_service.optimize(
            raw,
            result.title,
            flatten_transparency=is_wikimedia_svg,
        )
        if not local_path.is_file() or local_path.stat().st_size <= 0:
            raise RuntimeError("A imagem foi baixada, mas o arquivo final não pôde ser validado.")

        card.image_path = str(local_path)
        asset = MediaAsset(
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
        self.database.replace_card_media_asset(
            card.id,
            asset,
            project_id=card.project_id,
            image_path=card.image_path,
            update_image=True,
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

    def apply_best_image(
        self,
        project: ProjectData,
        card: FlashcardData,
        *,
        http_client: httpx.Client | None = None,
    ) -> FlashcardData:
        if not project.card_uses_component(card, "image"):
            raise ValueError("A estrutura deste cartão não utiliza imagens.")
        if self.has_valid_image(card):
            return card

        if card.image_path:
            card.image_path = ""
            self.database.update_card_media(card.id, project_id=card.project_id, image_path=card.image_path, update_image=True)

        errors: list[str] = []
        for term in self.preferred_search_terms(card):
            try:
                if isinstance(self.search_service, ImageSearchService):
                    results = self.search_service.search_provider_ordered(
                        term,
                        limit_per_provider=8,
                        client=http_client,
                    )
                elif hasattr(self.search_service, "search_provider_ordered"):
                    results = self.search_service.search_provider_ordered(term, limit_per_provider=8)
                else:
                    results = self.search_service.search(term, kind="image", limit=8)
            except Exception as exc:
                errors.append(f"{term}: {exc}")
                continue
            ranked_results = self._rank_relevant_results(card, term, list(results))
            if results and not ranked_results:
                errors.append(f"{term}: nenhum resultado atingiu relevância suficiente")
            for result in ranked_results:
                try:
                    return self.apply_search_result(
                        project,
                        card,
                        result,
                        http_client=http_client,
                    )
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
        asset = MediaAsset(
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
        self.database.replace_card_media_asset(
            card.id,
            asset,
            project_id=card.project_id,
            image_path=card.image_path,
            update_image=True,
        )
        return card

    def remove_image(self, card: FlashcardData) -> FlashcardData:
        if card.id is None:
            raise ValueError("Cartão sem identificador.")
        previous = card.image_path
        card.image_path = ""
        self.database.clear_card_media_asset(
            card.id,
            "image",
            project_id=card.project_id,
            image_path=card.image_path,
            update_image=True,
        )
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
