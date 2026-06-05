from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py → repo root is parents[2]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[1]

_ENV_FILES = (
    _PROJECT_ROOT / ".env",
    _BACKEND_ROOT / ".env",
    Path(".env"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=tuple(str(p) for p in _ENV_FILES if p.is_file()) or (".env",),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://cvats:cvats_dev_password@localhost:5432/cv_ats_scanner"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "change-me-to-a-random-64-char-string-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # S3 / MinIO
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin123"
    s3_bucket: str = "cv-ats-files"
    s3_region: str = "us-east-1"

    # AI
    llm_provider: str = "openai"
    embedding_provider: str = "local"
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    enable_ocr: bool = False
    enable_semantic_match: bool = False
    scoring_version: str = "1.2.0"
    max_upload_bytes: int = 5 * 1024 * 1024
    sync_tasks: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
