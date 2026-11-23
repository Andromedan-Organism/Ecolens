from typing import Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Validated input boundary for a search and its selected providers."""

    query: str = Field(min_length=1, max_length=300)
    sources: list[Literal["openverse", "wikimedia"]] = Field(
        default_factory=lambda: ["openverse", "wikimedia"],
        min_length=1,
        max_length=2,
    )


class ImageResult(BaseModel):
    """Normalized, validated image metadata shared across providers."""

    id: str
    title: str
    thumbnail: str
    source_url: str
    image_url: str
    creator: str
    license: str
    license_version: str
    license_url: str
    attribution: str
    source: str = "Openverse"
    width: int | None
    height: int | None


class SearchResponse(BaseModel):
    """Search results plus visible warnings for partially failed searches."""

    results: list[ImageResult]
    warnings: list[str] = Field(default_factory=list)
