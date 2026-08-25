from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "TalentOS Agent Builder Service"
    ENV: str = "local"
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    RELOAD: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # Security
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Encryption for provider credentials at rest (Fernet key, 32 url-safe base64 bytes).
    # Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = "vJb9YV8kQmT3Zr1cH0sXwF6nE4pL2aG7uD5oI9tK3yQ="

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/talentos_agent_builder"

    # Defaults for newly created agents (each agent can override)
    DEFAULT_TIMEOUT_SECONDS: float = 60
    DEFAULT_MAX_OUTPUT_TOKENS: int = 8192
    DEFAULT_RATE_LIMIT_PER_MINUTE: int = 60

    # --- IAM integration (this service is a relying party on iam-service's tokens) ---
    IAM_SERVICE_URL: str = "http://localhost:8003"
    IAM_JWKS_CACHE_TTL_SECONDS: int = 300

    # This service's own machine identity in iam-service (see scripts/bootstrap_iam_identity.py),
    # used only to call service-principal-management endpoints when publishing/rotating an
    # agent's invoke credential - never used for ordinary per-user permission checks.
    IAM_CLIENT_ID: str = ""
    IAM_CLIENT_SECRET: str = ""

    # --- Bootstrap-only (scripts/bootstrap_iam_identity.py, scripts/backfill_organization_id.py) ---
    IAM_BOOTSTRAP_ADMIN_EMAIL: str = "admin@talentos-platform.com"
    IAM_BOOTSTRAP_ADMIN_PASSWORD: str = "change-me-local-dev-password"
    BOOTSTRAP_ORGANIZATION_ID: str = "ea30b4e1-ea6a-4081-a816-755347c2bd6c"


@lru_cache
def get_settings() -> Settings:
    return Settings()
