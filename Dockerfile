FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS runtime

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY pyproject.toml README.md .python-version ./
RUN uv sync --no-dev

COPY src ./src
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "quotesquad.main:app", "--host", "0.0.0.0", "--port", "8000"]
