from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import os

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.models import SearchRequest, SearchResponse
from backend.app.providers import (
    OpenverseImageSearchProvider,
    ProviderError,
    WikimediaCommonsImageSearchProvider,
)
from backend.app.services import ImageSearchService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create providers once and inject them behind the shared service contract."""
    async with httpx.AsyncClient(
        timeout=10.0,
        headers={
            "User-Agent": (
                "EcoLens/0.4.0 "
                "(https://github.com/TherealArithmeticProgression/Ecolens)"
            )
        },
    ) as client:
        app.state.search_service = ImageSearchService(
            {
                "openverse": OpenverseImageSearchProvider(client),
                "wikimedia": WikimediaCommonsImageSearchProvider(client),
            }
        )
        yield


def get_search_service(request: Request) -> ImageSearchService:
    return request.app.state.search_service


app = FastAPI(title="EcoLens API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
async def search_images(
    request: SearchRequest,
    service: ImageSearchService = Depends(get_search_service),
) -> SearchResponse:
    try:
        return await service.search(request.query, request.sources)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
