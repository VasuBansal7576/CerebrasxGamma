from __future__ import annotations

import shutil
from typing import Literal

from pydantic import BaseModel, ConfigDict, SecretStr

from quotesquad.config import Settings

type ReadinessState = Literal["live", "configured", "local", "missing"]


class ReadinessItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: ReadinessState
    evidence: str
    blocks: str | None = None


class ProviderReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    providers: tuple[ReadinessItem, ...]


class InfraReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[ReadinessItem, ...]


def provider_readiness(settings: Settings) -> ProviderReadiness:
    tesseract_path = shutil.which("tesseract")
    providers = (
        _secret_provider(
            "cerebras", settings.cerebras_api_key, "Grounded synthesis uses fallback prose."
        ),
        ReadinessItem(
            name="nhtsa",
            status="live",
            evidence=f"{settings.nhtsa_base_url} public recalls and complaints APIs.",
        ),
        _secret_provider("mitchell", settings.mitchell_api_key, "Licensed auto labor-time lookup."),
        _secret_provider("chilton", settings.chilton_api_key, "Backup licensed auto labor lookup."),
        ReadinessItem(
            name="ebay_public_web",
            status="configured",
            evidence="Best-effort public search adapter; analysis reports a gap if eBay blocks it.",
        ),
        _secret_provider("ebay_motors", settings.ebay_api_key, "Retail parts price comparison."),
        _feed_provider("rockauto", settings.rockauto_feed_url, "Daily parts-price refresh."),
        _feed_provider("autozone", settings.autozone_feed_url, "Retail parts-price refresh."),
        _secret_provider(
            "amazon_products", settings.amazon_product_api_key, "Retail product lookup."
        ),
        _secret_provider("rsmeans", settings.rsmeans_api_key, "Contractor benchmark lookup."),
        _secret_provider("home_depot", settings.home_depot_api_key, "Contractor materials lookup."),
        _secret_provider("yelp", settings.yelp_api_key, "Alternative provider verification."),
        ReadinessItem(
            name="openstreetmap",
            status="live",
            evidence=(
                f"{settings.zippopotam_base_url} ZIP geocoding plus "
                f"{settings.overpass_base_url} and {settings.nominatim_base_url} "
                "public directory lookups."
            ),
            blocks="Licensing, ratings, and open-hours verification still require a richer provider.",
        ),
        _secret_provider("bbb", settings.bbb_api_key, "Complaint-history checks."),
        _feed_provider(
            "regulatory", settings.regulatory_feed_url, "State legal citation freshness."
        ),
        _secret_provider(
            "vision_ocr", settings.vision_ocr_api_key, "Photo OCR fallback for hard images."
        ),
        ReadinessItem(
            name="tesseract_ocr",
            status="live" if tesseract_path is not None else "missing",
            evidence=tesseract_path or "No tesseract binary found on PATH.",
            blocks=None if tesseract_path is not None else "Local image OCR.",
        ),
    )
    return ProviderReadiness(providers=providers)


def infra_readiness(settings: Settings) -> InfraReadiness:
    database_status: ReadinessState = (
        "configured" if settings.database_url.startswith("postgresql+") else "local"
    )
    database_blocks = None if database_status == "configured" else "Managed PostgreSQL/RDS rollout."
    return InfraReadiness(
        items=(
            ReadinessItem(
                name="database",
                status=database_status,
                evidence=settings.database_url.split("@")[-1],
                blocks=database_blocks,
            ),
            _endpoint("redis", settings.redis_url, "Session state and Redis Streams queue."),
            _endpoint("temporal", settings.temporal_address, "Durable workflow replay."),
            _endpoint(
                "object_storage", settings.object_storage_bucket, "24h raw-document staging."
            ),
            _endpoint("observability", settings.otel_exporter_otlp_endpoint, "Distributed traces."),
            _secret_provider(
                "pagerduty", settings.pagerduty_routing_key, "Production paging alerts."
            ),
            _endpoint("aws_secrets_manager", settings.aws_secrets_name, "Managed secret loading."),
        )
    )


def _secret_provider(name: str, secret: SecretStr | None, blocks: str) -> ReadinessItem:
    configured = secret is not None and secret.get_secret_value() != ""
    return ReadinessItem(
        name=name,
        status="configured" if configured else "missing",
        evidence="Credential present." if configured else "Credential not configured.",
        blocks=None if configured else blocks,
    )


def _feed_provider(name: str, value: str | None, blocks: str) -> ReadinessItem:
    evidence = value.strip() if value is not None else ""
    configured = evidence != ""
    return ReadinessItem(
        name=name,
        status="configured" if configured else "missing",
        evidence=evidence if configured else "Feed endpoint not configured.",
        blocks=None if configured else blocks,
    )


def _endpoint(name: str, value: str | None, blocks: str) -> ReadinessItem:
    evidence = value.strip() if value is not None else ""
    configured = evidence != ""
    return ReadinessItem(
        name=name,
        status="configured" if configured else "missing",
        evidence=evidence if configured else "Endpoint not configured.",
        blocks=None if configured else blocks,
    )
