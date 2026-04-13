"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    url: str = "sqlite+aiosqlite:///./data/tirithel.db"
    echo: bool = False

    model_config = {"env_prefix": "DB_"}


class LLMSettings(BaseSettings):
    anthropic_api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096

    model_config = {"env_prefix": "LLM_"}


class OCRSettings(BaseSettings):
    engine: str = "tesseract"
    language: str = "eng"
    confidence_threshold: float = 0.6

    model_config = {"env_prefix": "OCR_"}


class EmbeddingSettings(BaseSettings):
    model_name: str = "all-MiniLM-L6-v2"
    chroma_persist_dir: str = "./data/chromadb"

    model_config = {"env_prefix": "EMBEDDING_"}


class StorageSettings(BaseSettings):
    screenshot_dir: str = "./data/screenshots"

    model_config = {"env_prefix": "STORAGE_"}


class AppSettings(BaseSettings):
    app_name: str = "Tirithel"
    debug: bool = False
    api_prefix: str = "/api/v1"
    allowed_origins: str = "*"
    log_level: str = "INFO"
    screenshot_interval_seconds: int = 3

    database: DatabaseSettings = DatabaseSettings()
    llm: LLMSettings = LLMSettings()
    ocr: OCRSettings = OCRSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    storage: StorageSettings = StorageSettings()

    model_config = {"env_prefix": "APP_"}


def get_settings() -> AppSettings:
    return AppSettings()
