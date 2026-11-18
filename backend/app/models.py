from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class ImageResult(BaseModel):
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
    width: int | None
    height: int | None


class SearchResponse(BaseModel):
    results: list[ImageResult]
