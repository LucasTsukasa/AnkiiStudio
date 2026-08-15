from __future__ import annotations

import html
import re
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any, Literal

import httpx

from ankiistudio.models import WikimediaMediaResult


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "AnkiiStudio/0.11.0-beta.9 (https://github.com/LucasTsukasa)"


def _clean_metadata(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class WikimediaService:
    key = "wikimedia"
    label = "Wikimedia Commons"

    def __init__(self, timeout: float = 30.0, client: httpx.Client | None = None) -> None:
        self.timeout = timeout
        self._external_client = client

    @contextmanager
    def _client(self, *, timeout: float | None = None) -> Iterator[httpx.Client]:
        if self._external_client is not None:
            yield self._external_client
            return
        with httpx.Client(
            timeout=self.timeout if timeout is None else timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            yield client

    def search(
        self,
        term: str,
        *,
        kind: Literal["image", "audio"] = "image",
        limit: int = 12,
    ) -> list[WikimediaMediaResult]:
        if not term.strip():
            raise ValueError("Informe um termo de pesquisa.")
        limit = max(1, min(limit, 30))
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrsearch": term.strip(),
            "gsrnamespace": 6,
            "gsrlimit": limit * 3,
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": 900,
        }
        with self._client() as client:
            response = client.get(COMMONS_API, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        results: list[WikimediaMediaResult] = []
        pages = list(data.get("query", {}).get("pages", []))
        # Preserva explicitamente a ordem de relevância produzida pelo generator=search.
        pages.sort(key=lambda page: int(page.get("index", 10**9)))
        for page in pages:
            infos = page.get("imageinfo") or []
            if not infos:
                continue
            info = infos[0]
            mime = str(info.get("mime", ""))
            if kind == "image" and mime not in {
                "image/jpeg",
                "image/png",
                "image/webp",
                "image/gif",
                "image/tiff",
                "image/svg+xml",
            }:
                continue
            if kind == "audio" and not mime.startswith("audio/"):
                continue
            metadata = info.get("extmetadata") or {}
            results.append(
                WikimediaMediaResult(
                    provider="wikimedia",
                    title=str(page.get("title", "")),
                    page_id=page.get("pageid"),
                    file_url=str(info.get("url", "")),
                    thumbnail_url=str(info.get("thumburl", "")),
                    description_url=str(info.get("descriptionurl", "")),
                    mime=mime,
                    width=info.get("width"),
                    height=info.get("height"),
                    author=_clean_metadata(metadata.get("Artist")),
                    license_name=_clean_metadata(metadata.get("LicenseShortName")),
                    license_url=_clean_metadata(metadata.get("LicenseUrl")),
                    credit=_clean_metadata(metadata.get("Credit")),
                    description=_clean_metadata(metadata.get("ImageDescription")),
                )
            )
            if len(results) >= limit:
                break
        return results

    def download(self, url: str) -> tuple[bytes, str]:
        if not url.startswith("https://"):
            raise ValueError("A mídia do Wikimedia deve usar HTTPS.")
        with self._client(timeout=60) as client:
            response = client.get(url)
            response.raise_for_status()
        content_type = response.headers.get("content-type", "application/octet-stream")
        return response.content, content_type
