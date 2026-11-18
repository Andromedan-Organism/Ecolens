from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import os

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.models import SearchRequest, SearchResponse
from backend.app.providers import OpenverseImageSearchProvider, ProviderError
from backend.app.services import ImageSearchService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        app.state.search_service = ImageSearchService(
            OpenverseImageSearchProvider(client)
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
        results = await service.search(request.query)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return SearchResponse(results=results)
