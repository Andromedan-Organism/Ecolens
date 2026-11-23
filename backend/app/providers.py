from abc import ABC, abstractmethod
from html.parser import HTMLParser
import re
from typing import Any

import httpx

from backend.app.models import ImageResult


class ProviderError(Exception):
    """Raised when an upstream image provider cannot complete a search."""


class ImageSearchProvider(ABC):
    """Abstract contract shared by all image-search providers.

    The service depends on this interface rather than a particular catalog,
    so each implementation only needs to provide the same search operation.
    """

    @abstractmethod
    async def search(self, query: str, limit: int) -> list[ImageResult]:
        """Return normalized image results for a query."""


class OpenverseImageSearchProvider(ImageSearchProvider):
    """Openverse implementation of the provider contract.

    Inheriting from ``ImageSearchProvider`` makes this concrete class
    interchangeable with other provider implementations.
    """

    _API_URL = "https://api.openverse.org/v1/images/"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, limit: int) -> list[ImageResult]:
        try:
            response = await self._client.get(
                self._API_URL,
                params={
                    "q": query,
                    "page_size": limit,
                    "license_type": "commercial,modification",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderError("Openverse search is temporarily unavailable") from error

        raw_results = payload.get("results", []) if isinstance(payload, dict) else []
        return [
            result
            for item in raw_results
            if (result := self._to_image_result(item)) is not None
        ]

    @staticmethod
    def _to_image_result(item: Any) -> ImageResult | None:
        if not isinstance(item, dict) or not item.get("thumbnail"):
            return None

        source_url = item.get("foreign_landing_url") or item.get("url")
        if not source_url:
            return None

        return ImageResult(
            id=str(item.get("id") or ""),
            title=str(item.get("title") or "Untitled image"),
            thumbnail=str(item["thumbnail"]),
            source_url=str(source_url),
            image_url=str(item.get("url") or item["thumbnail"]),
            creator=str(item.get("creator") or "Creator not listed"),
            license=str(item.get("license") or "License not listed"),
            license_version=str(item.get("license_version") or ""),
            license_url=str(item.get("license_url") or ""),
            attribution=str(item.get("attribution") or ""),
            source="Openverse",
            width=OpenverseImageSearchProvider._positive_int(item.get("width")),
            height=OpenverseImageSearchProvider._positive_int(item.get("height")),
        )

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        try:
            dimension = int(value)
        except (TypeError, ValueError):
            return None
        return dimension if dimension > 0 else None


class _TextExtractor(HTMLParser):
    """Collect readable text from HTML-formatted Commons metadata."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


class WikimediaCommonsImageSearchProvider(ImageSearchProvider):
    """Wikimedia Commons implementation of the shared provider contract."""

    _API_URL = "https://commons.wikimedia.org/w/api.php"
    _ALLOWED_LICENSES = {
        "cc0": "cc0",
        "cc by": "cc-by",
        "cc by sa": "cc-by-sa",
        "public domain": "pdm",
        "public domain mark": "pdm",
    }

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, limit: int) -> list[ImageResult]:
        try:
            response = await self._client.get(
                self._API_URL,
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": query,
                    "gsrnamespace": 6,
                    "gsrlimit": limit,
                    "prop": "imageinfo",
                    "iiprop": "url|size|extmetadata",
                    "iiurlwidth": 400,
                    "format": "json",
                    "formatversion": 2,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderError(
                "Wikimedia Commons search is temporarily unavailable"
            ) from error

        pages = payload.get("query", {}).get("pages", []) if isinstance(payload, dict) else []
        if not isinstance(pages, list):
            return []

        return [
            result
            for page in pages
            if (result := self._to_image_result(page)) is not None
        ]

    @classmethod
    def _to_image_result(cls, page: Any) -> ImageResult | None:
        if not isinstance(page, dict):
            return None
        imageinfo = page.get("imageinfo")
        if not isinstance(imageinfo, list) or not imageinfo or not isinstance(imageinfo[0], dict):
            return None

        info = imageinfo[0]
        metadata = info.get("extmetadata")
        if not isinstance(metadata, dict):
            return None

        license_name = cls._metadata_text(metadata, "LicenseShortName")
        normalized_license = cls._normalize_license(license_name)
        if normalized_license is None:
            return None

        source_url = info.get("descriptionurl")
        image_url = info.get("url")
        thumbnail = info.get("thumburl") or image_url
        if not source_url or not image_url or not thumbnail:
            return None

        title = str(page.get("title") or "Untitled image")
        if title.startswith("File:"):
            title = title[5:]
        creator = cls._metadata_text(metadata, "Artist") or "Creator not listed"
        license_url = cls._metadata_text(metadata, "LicenseUrl")
        attribution = cls._metadata_text(metadata, "Attribution")
        if not attribution:
            attribution = f'"{title}" by {creator}'
        if license_name.lower() not in attribution.lower():
            attribution += f". {license_name}"
        if str(source_url) not in attribution:
            attribution += f". Source: {source_url}"

        return ImageResult(
            id=f"wikimedia:{page.get('pageid') or title}",
            title=title,
            thumbnail=str(thumbnail),
            source_url=str(source_url),
            image_url=str(image_url),
            creator=creator,
            license=normalized_license[0],
            license_version=normalized_license[1],
            license_url=license_url,
            attribution=attribution,
            source="Wikimedia Commons",
            width=cls._positive_int(info.get("width")),
            height=cls._positive_int(info.get("height")),
        )

    @classmethod
    def _normalize_license(cls, license_name: str) -> tuple[str, str] | None:
        normalized_name = re.sub(r"[\s-]+", " ", license_name.strip().lower())
        for name, code in cls._ALLOWED_LICENSES.items():
            if normalized_name == name:
                return code, ""
            if normalized_name.startswith(f"{name} "):
                suffix = normalized_name[len(name) + 1 :]
                version_match = re.fullmatch(
                    r"(\d+(?:\.\d+)?)(?: universal)?",
                    suffix,
                )
                if version_match:
                    return code, version_match.group(1)
        return None

    @staticmethod
    def _metadata_text(metadata: dict[str, Any], key: str) -> str:
        entry = metadata.get(key)
        if not isinstance(entry, dict) or not isinstance(entry.get("value"), str):
            return ""
        parser = _TextExtractor()
        parser.feed(entry["value"])
        return " ".join("".join(parser.parts).split())

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        try:
            dimension = int(value)
        except (TypeError, ValueError):
            return None
        return dimension if dimension > 0 else None
