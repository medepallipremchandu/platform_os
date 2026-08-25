from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "TalentOS IAM Service"
    ENV: str = "local"
    HOST: str = "0.0.0.0"
    PORT: int = 8003
    RELOAD: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # Security / CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/talentos_iam"

    # --- JWT / signing keys (RS256) ---
    JWT_PRIVATE_KEY_PATH: str = "./keys/private.pem"
    JWT_PUBLIC_KEY_PATH: str = "./keys/public.pem"
    JWT_KEY_ID: str = "iam-key-1"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Login lockout policy ---
    LOGIN_LOCKOUT_THRESHOLD: int = 10
    LOGIN_LOCKOUT_WINDOW_MINUTES: int = 15
    LOGIN_LOCKOUT_DURATION_MINUTES: int = 15

    # --- Password policy ---
    PASSWORD_MIN_LENGTH: int = 12

    # --- Password reset token lifetime ---
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Bootstrap (scripts/bootstrap.py only - not read by the running app) ---
    BOOTSTRAP_ORG_NAME: str = "TalentOS"
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@talentos-platform.com"
    BOOTSTRAP_ADMIN_PASSWORD: str = "change-me-local-dev-password"


@lru_cache
def get_settings() -> Settings:
    return Settings()
