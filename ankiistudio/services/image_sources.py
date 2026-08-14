from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import logging
import time
from typing import Iterable, Protocol

import httpx

from ankiistudio.config import SecretStore
from ankiistudio.constants import APP_VERSION
from ankiistudio.database import Database
from ankiistudio.models import ImageSearchResult
from ankiistudio.services.wikimedia_service import WikimediaService

USER_AGENT = f"AnkiiStudio/{APP_VERSION} (https://github.com/LucasTsukasa/AnkiiStudio)"
logger = logging.getLogger(__name__)


class ImageProvider(Protocol):
    key: str
    label: str

    def search(self, term: str, *, limit: int = 12) -> list[ImageSearchResult]: ...


class PixabayImageProvider:
    key = "pixabay"
    label = "Pixabay"
    API_URL = "https://pixabay.com/api/"

    def __init__(self, api_key: str, timeout: float = 30.0, client: httpx.Client | None = None) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout
        self._external_client = client

    def search(self, term: str, *, limit: int = 12) -> list[ImageSearchResult]:
        if not self.api_key:
            raise RuntimeError("Pixabay está habilitado, mas a API key não foi configurada.")
        client = self._external_client or httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        owns_client = self._external_client is None
        try:
            response = client.get(
                self.API_URL,
                params={
                    "key": self.api_key,
                    "q": term.strip(),
                    "image_type": "all",
                    "safesearch": "true",
                    "per_page": max(3, min(limit, 200)),
                },
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                client.close()
        results: list[ImageSearchResult] = []
        for item in payload.get("hits", []):
            file_url = str(item.get("largeImageURL") or item.get("webformatURL") or "")
            if not file_url:
                continue
            results.append(
                ImageSearchResult(
                    provider=self.key,
                    title=str(item.get("tags") or f"Pixabay #{item.get('id', '')}").strip(),
                    page_id=_as_int(item.get("id")),
                    file_url=file_url,
                    thumbnail_url=str(item.get("webformatURL") or item.get("previewURL") or ""),
                    description_url=str(item.get("pageURL") or ""),
                    width=_as_int(item.get("imageWidth")),
                    height=_as_int(item.get("imageHeight")),
                    author=str(item.get("user") or ""),
                    license_name="Pixabay Content License",
                    license_url="https://pixabay.com/service/license-summary/",
                    description=str(item.get("tags") or ""),
                )
            )
        return results


class PexelsImageProvider:
    key = "pexels"
    label = "Pexels"
    API_URL = "https://api.pexels.com/v1/search"

    def __init__(self, api_key: str, timeout: float = 30.0, client: httpx.Client | None = None) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout
        self._external_client = client

    def search(self, term: str, *, limit: int = 12) -> list[ImageSearchResult]:
        if not self.api_key:
            raise RuntimeError("Pexels está habilitado, mas a API key não foi configurada.")
        client = self._external_client or httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        owns_client = self._external_client is None
        try:
            response = client.get(
                self.API_URL,
                params={"query": term.strip(), "per_page": max(1, min(limit, 80))},
                headers={"Authorization": self.api_key},
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                client.close()
        results: list[ImageSearchResult] = []
        for item in payload.get("photos", []):
            sources = item.get("src") or {}
            file_url = str(sources.get("large") or sources.get("original") or "")
            if not file_url:
                continue
            results.append(
                ImageSearchResult(
                    provider=self.key,
                    title=str(item.get("alt") or f"Pexels #{item.get('id', '')}").strip(),
                    page_id=_as_int(item.get("id")),
                    file_url=file_url,
                    thumbnail_url=str(sources.get("medium") or sources.get("small") or ""),
                    description_url=str(item.get("url") or ""),
                    width=_as_int(item.get("width")),
                    height=_as_int(item.get("height")),
                    author=str(item.get("photographer") or ""),
                    license_name="Pexels License",
                    license_url="https://www.pexels.com/license/",
                    credit=str(item.get("photographer_url") or ""),
                    description=str(item.get("alt") or ""),
                )
            )
        return results


@dataclass(frozen=True)
class ImageSearchOutcome:
    results: list[ImageSearchResult]
    warnings: list[str]


class ImageSearchService:
    """Pesquisa nas fontes de imagem habilitadas nas Configurações.

    Wikimedia Commons permanece habilitado por padrão. Pixabay e Pexels são
    opcionais. A pesquisa manual pode restringir temporariamente a consulta a um
    subconjunto das fontes habilitadas, sem alterar a configuração global.
    """

    PROVIDER_LABELS = {
        "wikimedia": "Wikimedia Commons",
        "pixabay": "Pixabay",
        "pexels": "Pexels",
    }
    PROVIDER_KEYS = ("wikimedia", "pixabay", "pexels")

    def __init__(self, database: Database, timeout: float = 30.0) -> None:
        self.database = database
        self.timeout = timeout

    @contextmanager
    def client_session(self):
        """Reaproveita conexões HTTP durante uma pesquisa/operação em lote."""
        with httpx.Client(
            timeout=60,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            yield client

    @staticmethod
    def _enabled(database: Database, key: str, default: bool = False) -> bool:
        return database.get_setting(f"image_source_{key}", "1" if default else "0") == "1"

    def enabled_provider_keys(self) -> list[str]:
        keys: list[str] = []
        if self._enabled(self.database, "wikimedia", True):
            keys.append("wikimedia")
        if self._enabled(self.database, "pixabay"):
            keys.append("pixabay")
        if self._enabled(self.database, "pexels"):
            keys.append("pexels")
        return keys

    def _selected_provider_keys(self, provider_keys: Iterable[str] | None) -> list[str]:
        enabled = self.enabled_provider_keys()
        if provider_keys is None:
            return enabled
        requested = {str(key) for key in provider_keys}
        return [key for key in enabled if key in requested]

    def _providers(
        self,
        provider_keys: Iterable[str] | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> list[ImageProvider]:
        providers: list[ImageProvider] = []
        for key in self._selected_provider_keys(provider_keys):
            if key == "wikimedia":
                provider = WikimediaService(timeout=self.timeout, client=client)
                provider.key = "wikimedia"  # type: ignore[attr-defined]
                provider.label = "Wikimedia Commons"  # type: ignore[attr-defined]
                providers.append(provider)  # type: ignore[arg-type]
            elif key == "pixabay":
                providers.append(
                    PixabayImageProvider(
                        SecretStore.get("PIXABAY_API_KEY"),
                        timeout=self.timeout,
                        client=client,
                    )
                )
            elif key == "pexels":
                providers.append(
                    PexelsImageProvider(
                        SecretStore.get("PEXELS_API_KEY"),
                        timeout=self.timeout,
                        client=client,
                    )
                )
        return providers

    def _provider_search(self, provider: ImageProvider, term: str, *, limit: int) -> list[ImageSearchResult]:
        # A Pixabay exige cache de 24 horas para as consultas da API. O cache é
        # persistido no banco para continuar válido entre reinicializações.
        if getattr(provider, "key", "") != "pixabay":
            return provider.search(term, limit=limit)

        normalized_term = " ".join(term.casefold().split())
        digest = hashlib.sha256(f"{normalized_term}|{limit}".encode("utf-8")).hexdigest()[:32]
        cache_key = f"image_api_cache_pixabay_{digest}"
        raw = self.database.get_setting(cache_key, "")
        if raw:
            try:
                payload = json.loads(raw)
                if time.time() - float(payload.get("created_at", 0)) < 24 * 60 * 60:
                    return [ImageSearchResult.model_validate(item) for item in payload.get("results", [])]
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

        results = provider.search(term, limit=limit)
        self.database.set_setting(
            cache_key,
            json.dumps(
                {
                    "created_at": time.time(),
                    "results": [item.model_dump(mode="json") for item in results],
                },
                ensure_ascii=False,
            ),
        )
        return results

    def search_with_warnings(
        self,
        term: str,
        *,
        limit: int = 12,
        provider_keys: Iterable[str] | None = None,
        client: httpx.Client | None = None,
    ) -> ImageSearchOutcome:
        if client is None:
            with self.client_session() as session_client:
                return self.search_with_warnings(
                    term,
                    limit=limit,
                    provider_keys=provider_keys,
                    client=session_client,
                )
        providers = self._providers(provider_keys, client=client)
        if not providers:
            raise RuntimeError("Nenhuma fonte de imagem ativa foi selecionada para esta pesquisa.")
        per_provider = max(4, min(12, limit))
        buckets: list[list[ImageSearchResult]] = []
        warnings: list[str] = []
        for provider in providers:
            try:
                bucket = self._provider_search(provider, term, limit=per_provider)
            except Exception as exc:
                label = getattr(provider, "label", provider.__class__.__name__)
                logger.warning("Falha na fonte de imagem %s para %r: %s", label, term, exc)
                warnings.append(f"{label}: {exc}")
                continue
            buckets.append(bucket)

        # Intercala fontes para que uma biblioteca não monopolize a primeira tela.
        merged: list[ImageSearchResult] = []
        position = 0
        while len(merged) < limit:
            added = False
            for bucket in buckets:
                if position < len(bucket):
                    merged.append(bucket[position])
                    added = True
                    if len(merged) >= limit:
                        break
            if not added:
                break
            position += 1
        if not merged and warnings:
            raise RuntimeError("Não foi possível pesquisar imagens. " + " | ".join(warnings))
        return ImageSearchOutcome(merged, warnings)

    def search(
        self,
        term: str,
        *,
        kind: str = "image",
        limit: int = 12,
        provider_keys: Iterable[str] | None = None,
        client: httpx.Client | None = None,
    ) -> list[ImageSearchResult]:
        if kind != "image":
            raise ValueError("ImageSearchService pesquisa somente imagens.")
        return self.search_with_warnings(
            term,
            limit=limit,
            provider_keys=provider_keys,
            client=client,
        ).results

    def search_provider_ordered(
        self,
        term: str,
        *,
        limit_per_provider: int = 8,
        provider_keys: Iterable[str] | None = None,
        client: httpx.Client | None = None,
    ) -> list[ImageSearchResult]:
        if client is None:
            with self.client_session() as session_client:
                return self.search_provider_ordered(
                    term,
                    limit_per_provider=limit_per_provider,
                    provider_keys=provider_keys,
                    client=session_client,
                )
        results: list[ImageSearchResult] = []
        errors: list[str] = []
        providers = self._providers(provider_keys, client=client)
        if not providers:
            raise RuntimeError("Nenhuma fonte de imagem ativa foi selecionada para esta pesquisa.")
        for provider in providers:
            try:
                results.extend(self._provider_search(provider, term, limit=limit_per_provider))
            except Exception as exc:
                errors.append(f"{getattr(provider, 'label', provider.__class__.__name__)}: {exc}")
        if not results and errors:
            raise RuntimeError(" | ".join(errors))
        return results

    def download(self, url: str, *, client: httpx.Client | None = None) -> tuple[bytes, str]:
        if not url.startswith("https://"):
            raise ValueError("A imagem deve usar HTTPS.")
        if client is None:
            with self.client_session() as session_client:
                return self.download(url, client=session_client)
        response = client.get(url)
        response.raise_for_status()
        return response.content, response.headers.get("content-type", "application/octet-stream")


def _as_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
