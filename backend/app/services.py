import asyncio
from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit

from backend.app.models import ImageResult, SearchResponse
from backend.app.providers import ImageSearchProvider, ProviderError


class ImageSearchService:
    """Coordinate provider searches through their common abstraction.

    The selected implementations are stored in ``_providers`` and called
    polymorphically through ``ImageSearchProvider.search``. Callers use the
    public ``search`` method without managing provider state or merge details.
    """

    _MAX_QUERY_LENGTH = 300
    _MAX_RESULTS = 12

    def __init__(self, providers: Mapping[str, ImageSearchProvider]) -> None:
        self._providers = providers

    async def search(self, query: str, sources: list[str]) -> SearchResponse:
        """Validate a query, fan out to selected providers, and normalize results."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Query must not be empty")
        if len(normalized_query) > self._MAX_QUERY_LENGTH:
            raise ValueError(f"Query must be at most {self._MAX_QUERY_LENGTH} characters")

        selected_sources = list(dict.fromkeys(sources))
        if not selected_sources or any(
            source not in self._providers for source in selected_sources
        ):
            raise ValueError("Select at least one supported image source")

        outcomes = await asyncio.gather(
            *(
                self._providers[source].search(normalized_query, self._MAX_RESULTS)
                for source in selected_sources
            ),
            return_exceptions=True,
        )
        results_by_source: list[list[ImageResult]] = []
        failed_sources: list[str] = []
        for source, outcome in zip(selected_sources, outcomes):
            if isinstance(outcome, ProviderError):
                failed_sources.append(source)
            elif isinstance(outcome, BaseException):
                raise outcome
            else:
                results_by_source.append(outcome)

        if failed_sources and len(failed_sources) == len(selected_sources):
            raise ProviderError("All selected image sources are temporarily unavailable")

        results = self._merge_results(results_by_source)
        warnings = [
            f"{self._source_label(source)} search failed; showing results from other sources."
            for source in failed_sources
        ]
        return SearchResponse(results=results, warnings=warnings)

    @classmethod
    def _merge_results(cls, result_sets: list[list[ImageResult]]) -> list[ImageResult]:
        merged: list[ImageResult] = []
        seen_urls: set[str] = set()
        max_length = max((len(result_set) for result_set in result_sets), default=0)
        for index in range(max_length):
            for result_set in result_sets:
                if index >= len(result_set):
                    continue
                result = result_set[index]
                parsed_url = urlsplit(result.source_url)
                key = urlunsplit(
                    (
                        parsed_url.scheme.lower(),
                        parsed_url.netloc.lower(),
                        parsed_url.path.rstrip("/"),
                        "",
                        "",
                    )
                )
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                merged.append(result)
                if len(merged) == cls._MAX_RESULTS:
                    return merged
        return merged

    @staticmethod
    def _source_label(source: str) -> str:
        return "Wikimedia Commons" if source == "wikimedia" else "Openverse"
