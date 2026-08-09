from __future__ import annotations

import httpx

from ankiistudio.services.wikimedia_service import WikimediaService


class _Response:
    def __init__(self, payload) -> None:
        self._payload = payload
        self.status_code = 200
        self.headers = {"content-type": "application/json"}
        self.content = b""

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _Client:
    last_params = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        type(self).last_params = params
        return _Response(
            {
                "query": {
                    "pages": [
                        {
                            "pageid": 1,
                            "title": "File:Japanese Hiragana wo.svg",
                            "index": 1,
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/original.svg",
                                    "thumburl": "https://upload.wikimedia.org/900px-original.svg.png",
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Japanese_Hiragana_wo.svg",
                                    "mime": "image/svg+xml",
                                    "width": 512,
                                    "height": 512,
                                    "extmetadata": {},
                                }
                            ],
                        }
                    ]
                }
            }
        )


def test_search_accepts_svg_and_requests_large_raster_thumbnail(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "Client", _Client)
    results = WikimediaService().search("を", kind="image", limit=8)
    assert len(results) == 1
    assert results[0].mime == "image/svg+xml"
    assert results[0].thumbnail_url.endswith(".svg.png")
    assert _Client.last_params["iiurlwidth"] == 900
