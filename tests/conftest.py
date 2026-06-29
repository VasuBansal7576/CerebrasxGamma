from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quotesquad.config import get_settings


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("QUOTESQUAD_APP_ENV", "test")
    monkeypatch.setenv("QUOTESQUAD_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("QUOTESQUAD_RATE_LIMIT_PER_MINUTE", "0")
    get_settings.cache_clear()
    from quotesquad.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def admin_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("QUOTESQUAD_APP_ENV", "test")
    monkeypatch.setenv("QUOTESQUAD_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/admin.db")
    monkeypatch.setenv("QUOTESQUAD_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("QUOTESQUAD_API_KEY", "test-admin")
    get_settings.cache_clear()
    from quotesquad.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
