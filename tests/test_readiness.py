from __future__ import annotations

from fastapi.testclient import TestClient

from quotesquad.readiness import InfraReadiness, ProviderReadiness


def test_provider_and_infra_readiness_are_not_public(client: TestClient) -> None:
    providers = client.get("/api/providers/status")
    infra = client.get("/api/infra/readiness")
    assert providers.status_code == 404
    assert infra.status_code == 404


def test_provider_and_infra_readiness_surfaces_for_admin(admin_client: TestClient) -> None:
    headers = {"x-quotesquad-key": "test-admin"}
    providers = admin_client.get("/api/providers/status", headers=headers)
    infra = admin_client.get("/api/infra/readiness", headers=headers)
    assert providers.status_code == 200
    assert infra.status_code == 200
    provider_payload = ProviderReadiness.model_validate_json(providers.text)
    infra_payload = InfraReadiness.model_validate_json(infra.text)
    provider_names = {item.name for item in provider_payload.providers}
    infra_names = {item.name for item in infra_payload.items}
    assert {"cerebras", "mitchell", "openstreetmap", "tesseract_ocr"} <= provider_names
    assert {"database", "redis", "temporal", "object_storage", "observability"} <= infra_names


def test_home_page_does_not_expose_provider_readiness(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "/api/providers/status" not in response.text
    assert "Mitchell" not in response.text
