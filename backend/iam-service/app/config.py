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

    # --- Outbound notifications (producer only - notification-service owns the consumer) ---
    # iam-service publishes "notifications.send_email" onto this broker and never reads from it.
    # Must match notification-service's NOTIFICATIONS_BROKER_URL. Note the "sqla+" scheme: Kombu's
    # SQLAlchemy transport parses it itself, and it is NOT the same form SQLAlchemy's own
    # create_engine() takes.
    NOTIFICATIONS_BROKER_URL: str = "sqla+postgresql://postgres:postgres@localhost:5432/talentos_notifications"
    NOTIFICATIONS_QUEUE_NAME: str = "notifications"
    # Kill switch. False makes every send a log line instead of a publish - useful for tests and
    # for a deployment where no worker exists yet.
    NOTIFICATIONS_ENABLED: bool = True

    # Base URL of `portal`, the platform's single login page. Invite and password-reset emails
    # link to its /set-password page, which is the one landing spot for both flows.
    PORTAL_URL: str = "http://localhost:5175"

    # --- Bootstrap (scripts/bootstrap.py only - not read by the running app) ---
    # The ONE seeded account: the platform administrator. is_superadmin=True and no organization
    # membership, because the tier sits above organizations - it creates them (and their first
    # admins) through the console. Nothing else is seeded; there is no starter organization,
    # because creating one is exactly what this account exists to do.
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@talentos-platform.com"
    BOOTSTRAP_ADMIN_PASSWORD: str = "change-me-local-dev-password"


@lru_cache
def get_settings() -> Settings:
    return Settings()
