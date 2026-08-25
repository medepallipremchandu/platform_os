from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "TalentOS Notification Service"
    ENV: str = "local"
    HOST: str = "0.0.0.0"
    PORT: int = 8104
    RELOAD: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # Security / CORS - the provider-configuration API is called from iam-console.
    CORS_ORIGINS: str = "http://localhost:5174"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # --- Database ---
    # Plain SQLAlchemy access to the same talentos_notifications database, used for the EmailLog
    # audit table and the per-organization provider configs (app/models.py). Kept as its own
    # setting - not derived from NOTIFICATIONS_BROKER_URL - because it's a normal
    # "postgresql+psycopg2://" DSN for SQLAlchemy's own engine, while NOTIFICATIONS_BROKER_URL needs the
    # "sqla+postgresql://" scheme Kombu's SQLAlchemy transport expects. Two settings, one
    # physical database, two URL dialects.
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/talentos_notifications"

    # --- Celery: the PLATFORM broker (tier-1 ingest) ---
    # Every producer (iam-service today) publishes `notifications.send_email` here, always.
    # It is deliberately NOT tenant-configurable: a tenant misconfiguring their own broker must
    # never be able to break organization creation or a password reset. An organization's own
    # queue provider, when enabled, is a SECOND hop the dispatcher re-publishes onto - see
    # app/providers/queue/ and the "Two-tier queueing" section of README.md.
    #
    # Postgres via Kombu's SQLAlchemy transport: no Redis/RabbitMQ operational dependency for
    # what is, for now, low-volume transactional email. Same physical database as DATABASE_URL
    # above, different URL scheme because Kombu's SQLAlchemy transport parses the scheme itself
    # to pick its own dialect/driver rather than reusing SQLAlchemy's create_engine() parsing.
    NOTIFICATIONS_BROKER_URL: str = "sqla+postgresql://postgres:postgres@localhost:5432/talentos_notifications"
    NOTIFICATIONS_QUEUE_NAME: str = "notifications"
    NOTIFICATIONS_MAX_RETRIES: int = 3
    NOTIFICATIONS_RETRY_BACKOFF_SECONDS: int = 10

    # --- Platform-default email provider (used by any org with no enabled email provider) ---
    # If SMTP_HOST is empty the platform default resolves to the "console" provider instead: the
    # fully-rendered email is logged at INFO level (link and token included) and EmailLog.status
    # is recorded as "logged_no_smtp_configured". This sandboxed dev environment has no real SMTP
    # credentials, and this matches the convention iam-service's password_reset_service already
    # uses.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_ADDRESS: str = "no-reply@talentos-platform.com"
    SMTP_USE_TLS: bool = True
    # Set false only for a relay with a self-signed or internal-CA certificate. The connection
    # stays encrypted; only the identity check is dropped. Never the right answer for a public
    # provider (Google Workspace, SES, SendGrid) - a verification failure there means something
    # is genuinely wrong.
    SMTP_VERIFY_CERT: bool = True

    # --- Provider secret encryption (Fernet) ---
    # Tenant provider secrets (SMTP passwords, SendGrid API keys, broker DSNs) are encrypted at
    # rest with this key and never returned by the API - the same write-only posture iam-service
    # uses for service-principal secrets. Generate one with:
    #     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Empty in a fresh checkout: startup refuses to store secrets until it is set.
    PROVIDER_SECRET_KEY: str = ""

    # --- IAM (this service is a relying party on iam-service's RS256 tokens) ---
    IAM_SERVICE_URL: str = "http://localhost:8113"
    IAM_JWKS_URL: str = "http://localhost:8113/.well-known/jwks.json"
    IAM_JWKS_CACHE_SECONDS: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
