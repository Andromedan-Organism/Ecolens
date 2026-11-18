from backend.app.models import ImageResult
from backend.app.providers import ImageSearchProvider


class ImageSearchService:
    _MAX_QUERY_LENGTH = 300
    _MAX_RESULTS = 12

    def __init__(self, provider: ImageSearchProvider) -> None:
        self._provider = provider

    async def search(self, query: str) -> list[ImageResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Query must not be empty")
        if len(normalized_query) > self._MAX_QUERY_LENGTH:
            raise ValueError(f"Query must be at most {self._MAX_QUERY_LENGTH} characters")
        return await self._provider.search(normalized_query, self._MAX_RESULTS)
