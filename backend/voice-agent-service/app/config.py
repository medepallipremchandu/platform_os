from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Infra-level settings only. Per-org telephony provider credentials live encrypted in the
    database (see app/models/telephony_provider.py); per-call AI credentials don't exist at all
    here - conversation generation is delegated to agent-builder-service (see
    app/services/conversation_client.py), never called directly from this service.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "TalentOS Voice Agent Service"
    ENV: str = "local"
    HOST: str = "0.0.0.0"
    PORT: int = 8004
    RELOAD: bool = True
    LOG_LEVEL: str = "INFO"

    # Security
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/talentos_voice_agent"

    # Public URL this service is reachable at, used to build Twilio webhook callback URLs
    # (voice/status). Twilio must be able to reach this over the public internet - in local dev
    # this means a tunnel (e.g. `ngrok http 8004` or `cloudflared tunnel --url http://localhost:8004`)
    # and setting BASE_URL to the tunnel's https URL. Without a real, publicly reachable BASE_URL,
    # Twilio cannot call back into this service and no live call will ever progress past DIALING.
    BASE_URL: str = "http://localhost:8004"

    # Fernet key used to encrypt telephony provider credentials at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    CREDENTIAL_ENCRYPTION_KEY: str = "vJb9YV8kQmT3Zr1cH0sXwF6nE4pL2aG7uD5oI9tK3yQ="

    # How often the retry-scheduling background loop polls for due retries.
    RETRY_POLL_INTERVAL_SECONDS: int = 60

    # --- iam-service: this service is a Bearer-token relying party (see app/core/iam_client.py) ---
    IAM_SERVICE_URL: str = "http://localhost:8003"
    IAM_JWKS_CACHE_TTL_SECONDS: int = 300

    # This service's own machine identity in iam-service (scripts/bootstrap_iam_identity.py fills
    # these in). Used only to call iam-service on behalf of the two Twilio webhook endpoints
    # (which have no end-user bearer token of their own) when posting a system-attributed audit
    # event - never used for ordinary per-user permission checks.
    IAM_CLIENT_ID: str = ""
    IAM_CLIENT_SECRET: str = ""

    # --- Bootstrap-only (scripts/bootstrap_iam_identity.py) ---
    IAM_BOOTSTRAP_ADMIN_EMAIL: str = "admin@talentos-platform.com"
    IAM_BOOTSTRAP_ADMIN_PASSWORD: str = "change-me-local-dev-password"
    BOOTSTRAP_ORGANIZATION_ID: str = ""

    # --- agent-builder-service: conversation generation is 3 published agents, never a direct
    # model/provider call from this service. Each pair is a resource-bound IAM Service Principal
    # credential minted by scripts/seed_call_agents.py. ---
    AGENT_BUILDER_SERVICE_URL: str = "http://localhost:8002/api/v1"
    AGENT_INVOKE_TIMEOUT_SECONDS: float = 30.0

    CONSENT_TURN_AGENT_CLIENT_ID: str = ""
    CONSENT_TURN_AGENT_CLIENT_SECRET: str = ""
    MAIN_TURN_AGENT_CLIENT_ID: str = ""
    MAIN_TURN_AGENT_CLIENT_SECRET: str = ""
    SUMMARY_AGENT_CLIENT_ID: str = ""
    SUMMARY_AGENT_CLIENT_SECRET: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
