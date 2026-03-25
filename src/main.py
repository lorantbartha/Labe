import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiohttp
from aiodynamo.client import Client
from aiodynamo.credentials import Credentials
from aiodynamo.http.aiohttp import AIOHTTP
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic_ai.exceptions import ModelHTTPError
from yarl import URL

from app_config import app_config
from core.exceptions import ResourceNotFoundError
from goals.router import router as goals_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "info").upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    session = aiohttp.ClientSession()
    endpoint = URL(app_config.aws_endpoint_url) if app_config.aws_endpoint_url else None
    app.state.dynamo_client = Client(
        http=AIOHTTP(session),
        credentials=Credentials.auto(),
        region=app_config.aws_region,
        endpoint=endpoint,
    )
    app.state.aiohttp_session = session
    logger.info("DynamoDB client initialised (endpoint=%s)", endpoint)
    try:
        yield
    finally:
        await session.close()
        logger.info("aiohttp session closed")


app = FastAPI(
    title="Labe",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(goals_router, prefix="/goals", tags=["goals"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.exception_handler(ResourceNotFoundError)
async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.detail})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ModelHTTPError)
async def openai_model_error_handler(request: Request, exc: ModelHTTPError) -> JSONResponse:
    logger.error("OpenAI model request failed", exc_info=exc)
    detail = "OpenAI model request failed."
    if exc.status_code in {401, 403}:
        detail = (
            "OpenAI model access failed. Check OPENAI_API_KEY and model access, or set "
            f"OPENAI_FAST_MODEL / OPENAI_REASONING_MODEL to models your project can use. "
            f"Current values: {app_config.openai_fast_model}, {app_config.openai_reasoning_model}."
        )
    return JSONResponse(status_code=502, content={"detail": detail})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
