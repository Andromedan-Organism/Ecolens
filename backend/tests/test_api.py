import unittest

import httpx

from backend.app.main import app, get_search_service
from backend.app.models import ImageResult
from backend.app.providers import (
    ImageSearchProvider,
    OpenverseImageSearchProvider,
    ProviderError,
)
from backend.app.services import ImageSearchService


class StubProvider(ImageSearchProvider):
    def __init__(self) -> None:
        self.query: str | None = None
        self.limit: int | None = None

    async def search(self, query: str, limit: int) -> list[ImageResult]:
        self.query = query
        self.limit = limit
        return [
            ImageResult(
                id="image-1",
                title="Blue flower",
                thumbnail="https://images.example/thumb.jpg",
                source_url="https://images.example/source",
                image_url="https://images.example/image.jpg",
                creator="A. Artist",
                license="cc-by",
                license_version="4.0",
                license_url="https://creativecommons.org/licenses/by/4.0/",
                attribution="Blue flower by A. Artist",
                width=1200,
                height=800,
            )
        ]


class ImageSearchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_uses_provider_contract_and_normalizes_query(self) -> None:
        provider = StubProvider()
        service = ImageSearchService(provider)

        results = await service.search("  blue flower  ")

        self.assertEqual(provider.query, "blue flower")
        self.assertEqual(provider.limit, 12)
        self.assertEqual(results[0].license_version, "4.0")

    async def test_service_rejects_empty_or_overlong_queries(self) -> None:
        service = ImageSearchService(StubProvider())

        with self.assertRaisesRegex(ValueError, "must not be empty"):
            await service.search("   ")
        with self.assertRaisesRegex(ValueError, "at most 300"):
            await service.search("x" * 301)


class OpenverseProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_maps_openverse_result_metadata(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params["q"], "blue flower")
            self.assertEqual(request.url.params["page_size"], "12")
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "image-1",
                            "title": "Blue flower",
                            "thumbnail": "https://images.example/thumb.jpg",
                            "url": "https://images.example/image.jpg",
                            "foreign_landing_url": "https://images.example/source",
                            "creator": "A. Artist",
                            "license": "cc-by",
                            "license_version": "4.0",
                            "license_url": "https://creativecommons.org/licenses/by/4.0/",
                            "width": 1200,
                            "height": "800",
                        },
                        {"thumbnail": "https://images.example/no-source.jpg"},
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenverseImageSearchProvider(client)
            results = await provider.search("blue flower", 12)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_url, "https://images.example/source")
        self.assertEqual(results[0].license_version, "4.0")
        self.assertEqual(results[0].height, 800)

    async def test_provider_surfaces_upstream_errors(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(503)
            )
        ) as client:
            provider = OpenverseImageSearchProvider(client)

            with self.assertRaises(ProviderError):
                await provider.search("blue flower", 12)


class SearchApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.provider = StubProvider()
        app.dependency_overrides[get_search_service] = lambda: ImageSearchService(
            self.provider
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    async def test_search_returns_normalized_result(self) -> None:
        response = await self.client.post("/api/search", json={"query": "blue flower"})

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["source_url"], "https://images.example/source")
        self.assertEqual(result["license_version"], "4.0")
        self.assertEqual(self.provider.query, "blue flower")

    async def test_search_rejects_empty_query(self) -> None:
        response = await self.client.post("/api/search", json={"query": ""})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
