.PHONY: dev test lint typecheck check

dev:
	PYTHONPATH=src uv run uvicorn quotesquad.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run basedpyright

check: lint typecheck test
