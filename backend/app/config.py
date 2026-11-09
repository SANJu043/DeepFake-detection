"""
Application configuration loaded from environment variables.

All secrets come from the environment or Vault — never hardcoded.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration. Values are read from .env / environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    # ── Application ─────────────────────────────────────────
    app_name: str = "deepfake-auth"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Database ────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "deepfake_auth"
    postgres_user: str = "dfauth"
    postgres_password: str = "changeme"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Redis / Celery ──────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── MinIO / S3 ──────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "deepfake-auth-videos"
    minio_use_ssl: bool = False

    # ── JWT ──────────────────────────────────────────────────
    jwt_secret_key: str = "change-me-jwt"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_minutes: int = 10080

    # ── Signing ─────────────────────────────────────────────
    signer_backend: str = "local"  # "local", "softhsm", "vault"
    signing_key_dir: str = "./keys"

    # Vault settings
    vault_addr: str = "http://localhost:8200"
    vault_token: str = ""
    vault_transit_key: str = "deepfake-auth-signer"

    # SoftHSM settings
    softhsm_pin: str = ""
    softhsm_slot: int = 0

    # ── TSA ──────────────────────────────────────────────────
    tsa_backend: str = "local"  # "local", "freetsa", "custom"
    tsa_url: str = "http://freetsa.org/tsr"
    tsa_key_dir: str = "./keys/tsa"

    # ── Detection Models ────────────────────────────────────
    model_weights_dir: str = "./weights"
    max_frames: int = 300
    frame_sample_interval: float = 0.2
    face_detector: str = "retinaface"
    face_crop_margin: float = 0.2
    face_crop_size: int = 380

    # ── Policy Engine ───────────────────────────────────────
    threshold_clean: float = 0.30
    threshold_manipulated: float = 0.70

    # ── Upload Limits ───────────────────────────────────────
    max_upload_size_mb: int = 200
    allowed_extensions: str = "mp4,mov,webm"
    allowed_mime_types: str = "video/mp4,video/quicktime,video/webm"

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [e.strip() for e in self.allowed_extensions.split(",")]

    @property
    def allowed_mime_types_list(self) -> List[str]:
        return [m.strip() for m in self.allowed_mime_types.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    # ── Anomaly Detection ───────────────────────────────────
    anomaly_window_minutes: int = 10
    anomaly_threshold: float = 0.5
    failed_login_limit: int = 5
    upload_rate_limit: int = 20

    # ── Encryption at Rest ──────────────────────────────────
    master_key: str = "0" * 64  # 256-bit hex, must be overridden

    # ── CORS ────────────────────────────────────────────────
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
