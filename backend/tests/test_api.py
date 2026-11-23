import unittest

import httpx

from backend.app.main import app, get_search_service
from backend.app.models import ImageResult
from backend.app.providers import (
    ImageSearchProvider,
    OpenverseImageSearchProvider,
    ProviderError,
    WikimediaCommonsImageSearchProvider,
)
from backend.app.services import ImageSearchService


class StubProvider(ImageSearchProvider):
    def __init__(self) -> None:
        self.query: str | None = None
        self.limit: int | None = None
        self.calls = 0

    async def search(self, query: str, limit: int) -> list[ImageResult]:
        self.calls += 1
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
        service = ImageSearchService({"openverse": provider})

        response = await service.search("  blue flower  ", ["openverse"])

        self.assertEqual(provider.query, "blue flower")
        self.assertEqual(provider.limit, 12)
        self.assertEqual(response.results[0].license_version, "4.0")

    async def test_service_rejects_empty_or_overlong_queries(self) -> None:
        service = ImageSearchService({"openverse": StubProvider()})

        with self.assertRaisesRegex(ValueError, "must not be empty"):
            await service.search("   ", ["openverse"])
        with self.assertRaisesRegex(ValueError, "at most 300"):
            await service.search("x" * 301, ["openverse"])

    async def test_service_deduplicates_results_and_reports_partial_source_failure(self) -> None:
        class FailingProvider(ImageSearchProvider):
            async def search(self, query: str, limit: int) -> list[ImageResult]:
                raise ProviderError("source unavailable")

        openverse = StubProvider()
        commons = StubProvider()
        response = await ImageSearchService(
            {"openverse": openverse, "wikimedia": commons}
        ).search("blue flower", ["openverse", "wikimedia"])

        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.warnings, [])

        partial_response = await ImageSearchService(
            {"openverse": openverse, "wikimedia": FailingProvider()}
        ).search("blue flower", ["openverse", "wikimedia"])
        self.assertEqual(len(partial_response.results), 1)
        self.assertEqual(len(partial_response.warnings), 1)
        self.assertIn("Wikimedia Commons", partial_response.warnings[0])

    async def test_service_rejects_an_empty_source_selection(self) -> None:
        service = ImageSearchService({"openverse": StubProvider()})

        with self.assertRaisesRegex(ValueError, "at least one"):
            await service.search("blue flower", [])


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
        self.assertEqual(results[0].source, "Openverse")

    async def test_provider_surfaces_upstream_errors(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(503)
            )
        ) as client:
            provider = OpenverseImageSearchProvider(client)

            with self.assertRaises(ProviderError):
                await provider.search("blue flower", 12)


class WikimediaCommonsProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_maps_reusable_license_metadata_and_skips_restricted_results(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params["gsrsearch"], "blue flower")
            self.assertEqual(request.url.params["gsrnamespace"], "6")
            return httpx.Response(
                200,
                json={
                    "query": {
                        "pages": [
                            {
                                "pageid": 42,
                                "title": "File:Blue flower.jpg",
                                "imageinfo": [
                                    {
                                        "url": "https://upload.wikimedia.org/blue.jpg",
                                        "thumburl": "https://upload.wikimedia.org/thumb.jpg",
                                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Blue_flower.jpg",
                                        "width": 1200,
                                        "height": 800,
                                        "extmetadata": {
                                            "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                            "LicenseUrl": {
                                                "value": "https://creativecommons.org/licenses/by-sa/4.0/"
                                            },
                                            "Artist": {"value": "<a>A. Artist</a>"},
                                        },
                                    }
                                ],
                            },
                            {
                                "pageid": 43,
                                "title": "File:Restricted.jpg",
                                "imageinfo": [
                                    {
                                        "url": "https://upload.wikimedia.org/restricted.jpg",
                                        "thumburl": "https://upload.wikimedia.org/restricted-thumb.jpg",
                                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Restricted.jpg",
                                        "extmetadata": {
                                            "LicenseShortName": {"value": "CC BY-NC 4.0"}
                                        },
                                    }
                                ],
                            },
                        ]
                    }
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = WikimediaCommonsImageSearchProvider(client)
            results = await provider.search("blue flower", 12)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Blue flower.jpg")
        self.assertEqual(results[0].creator, "A. Artist")
        self.assertEqual(results[0].license, "cc-by-sa")
        self.assertEqual(results[0].license_version, "4.0")
        self.assertEqual(results[0].source, "Wikimedia Commons")
        self.assertEqual(results[0].width, 1200)

    async def test_provider_surfaces_upstream_errors(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(503))
        ) as client:
            provider = WikimediaCommonsImageSearchProvider(client)

            with self.assertRaises(ProviderError):
                await provider.search("blue flower", 12)


class SearchApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.provider = StubProvider()
        self.commons_provider = StubProvider()
        app.dependency_overrides[get_search_service] = lambda: ImageSearchService(
            {"openverse": self.provider, "wikimedia": self.commons_provider}
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    async def test_search_returns_normalized_result(self) -> None:
        response = await self.client.post(
            "/api/search",
            json={"query": "blue flower", "sources": ["openverse"]},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["source_url"], "https://images.example/source")
        self.assertEqual(result["license_version"], "4.0")
        self.assertEqual(self.provider.query, "blue flower")
        self.assertEqual(self.commons_provider.calls, 0)

    async def test_search_rejects_empty_query(self) -> None:
        response = await self.client.post("/api/search", json={"query": ""})

        self.assertEqual(response.status_code, 422)

    async def test_search_defaults_to_both_sources(self) -> None:
        response = await self.client.post("/api/search", json={"query": "blue flower"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(self.commons_provider.calls, 1)

    async def test_search_rejects_unsupported_source(self) -> None:
        response = await self.client.post(
            "/api/search",
            json={"query": "blue flower", "sources": ["unknown"]},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
