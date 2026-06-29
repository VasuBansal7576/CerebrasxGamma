from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from quotesquad.config import get_settings
from quotesquad.db import configure_database, dispose_database
from quotesquad.routers import api, web

RateBuckets = defaultdict[str, deque[float]]
_rate_buckets: RateBuckets = defaultdict(deque)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    await configure_database(settings)
    yield
    await dispose_database()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="QuoteSquad",
        debug=settings.app_env != "prod",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory="src/quotesquad/static"), name="static")
    app.include_router(api.router)
    app.include_router(web.router)
    _ = app.middleware("http")(_rate_limit)
    return app


async def _rate_limit(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    settings = get_settings()
    if settings.rate_limit_per_minute == 0:
        return await call_next(request)
    client = request.client.host if request.client is not None else "unknown"
    now = time.monotonic()
    bucket = _rate_buckets[client]
    while bucket and now - bucket[0] > 60:
        _ = bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
    bucket.append(now)
    return await call_next(request)


app = create_app()
