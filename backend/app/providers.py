from abc import ABC, abstractmethod
from typing import Any

import httpx

from backend.app.models import ImageResult


class ProviderError(Exception):
    """Raised when an upstream image provider cannot complete a search."""


class ImageSearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int) -> list[ImageResult]:
        """Return normalized image results for a query."""


class OpenverseImageSearchProvider(ImageSearchProvider):
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
