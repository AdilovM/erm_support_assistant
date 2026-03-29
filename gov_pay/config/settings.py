"""Application configuration using pydantic-settings."""

from typing import Optional

from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    url: str = "postgresql+asyncpg://localhost:5432/gov_pay"
    echo: bool = False
    pool_size: int = 20
    max_overflow: int = 10

    model_config = {"env_prefix": "DB_"}


class GatewaySettings(BaseSettings):
    default_provider: str = "stripe"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""

    # Authorize.net
    authnet_api_login_id: str = ""
    authnet_transaction_key: str = ""
    authnet_sandbox: bool = True

    model_config = {"env_prefix": "GATEWAY_"}


class ERMSettings(BaseSettings):
    tyler_tech_api_url: str = ""
    tyler_tech_api_key: str = ""
    tyler_tech_api_secret: str = ""
    tyler_tech_timeout: int = 30

    model_config = {"env_prefix": "ERM_"}


class AppSettings(BaseSettings):
    app_name: str = "Government Payment System"
    debug: bool = False
    api_prefix: str = "/api/v1"
    allowed_origins: str = "http://localhost:8000"
    log_level: str = "INFO"

    # Security
    api_key_header: str = "X-API-Key"
    jwt_secret: str = ""  # REQUIRED — must be set via APP_JWT_SECRET env var
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    # API keys — comma-separated list of valid keys for bootstrapping
    # In production, use database-backed API key management
    api_keys: str = ""  # e.g., "key1,key2,key3"

    # Transaction settings
    transaction_number_prefix: str = "GOV"
    refund_number_prefix: str = "REF"
    max_refund_days: int = 180  # Maximum days after payment to allow refund
    void_window_hours: int = 24  # Hours after authorization to allow void

    database: DatabaseSettings = DatabaseSettings()
    gateway: GatewaySettings = GatewaySettings()
    erm: ERMSettings = ERMSettings()

    model_config = {"env_prefix": "APP_"}


def get_settings() -> AppSettings:
    return AppSettings()
