from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

type AppEnv = Literal["dev", "test", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QUOTESQUAD_",
        extra="ignore",
    )

    app_env: AppEnv = "dev"
    database_url: str = "sqlite+aiosqlite:///./data/quotesquad.db"
    public_base_url: str = "http://localhost:8000"
    api_key: SecretStr | None = None
    cerebras_api_key: SecretStr | None = None
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_model: str = "gemma-4-31b"
    nhtsa_base_url: str = "https://api.nhtsa.gov"
    zippopotam_base_url: str = "https://api.zippopotam.us"
    overpass_base_url: str = "https://overpass-api.de/api"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    mitchell_api_key: SecretStr | None = None
    chilton_api_key: SecretStr | None = None
    ebay_api_key: SecretStr | None = None
    rockauto_feed_url: str | None = None
    autozone_feed_url: str | None = None
    amazon_product_api_key: SecretStr | None = None
    rsmeans_api_key: SecretStr | None = None
    home_depot_api_key: SecretStr | None = None
    yelp_api_key: SecretStr | None = None
    bbb_api_key: SecretStr | None = None
    regulatory_feed_url: str | None = None
    vision_ocr_api_key: SecretStr | None = None
    redis_url: str | None = None
    temporal_address: str | None = None
    object_storage_bucket: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    pagerduty_routing_key: SecretStr | None = None
    aws_secrets_name: str | None = None
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    rate_limit_per_minute: int = Field(default=60, ge=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
