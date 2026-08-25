from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "TalentOS Intake & Matching Service"
    ENV: str = "local"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # Security
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # --- iam-service: this service is a Bearer-token relying party (see app/core/iam_client.py) ---
    IAM_SERVICE_URL: str = "http://localhost:8003"
    IAM_JWKS_CACHE_TTL_SECONDS: int = 300

    # One-time value used only by scripts/backfill_organization_id.py to stamp existing rows.
    BOOTSTRAP_ORGANIZATION_ID: str = ""

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/talentos_app"

    # --- agent-builder-service: every AI call goes through an agent, no hardcoded models/prompts here ---
    # Each agent's invoke credential is now an IAM-issued, resource-bound Service Principal
    # (client_id/client_secret) instead of a static agtk_... key - see app/core/iam_client.py's
    # AgentCredentialTokenCache and app/services/agent_client.py.
    AGENT_BUILDER_SERVICE_URL: str = "http://localhost:8002/api/v1"
    AGENT_INVOKE_TIMEOUT_SECONDS: float = 90.0

    JD_ANALYSIS_AGENT_CLIENT_ID: str = ""
    JD_ANALYSIS_AGENT_CLIENT_SECRET: str = ""
    RESUME_ANALYSIS_AGENT_CLIENT_ID: str = ""
    RESUME_ANALYSIS_AGENT_CLIENT_SECRET: str = ""
    MATCHING_AGENT_CLIENT_ID: str = ""
    MATCHING_AGENT_CLIENT_SECRET: str = ""
    QUESTION_GEN_DESCRIPTIVE_AGENT_CLIENT_ID: str = ""
    QUESTION_GEN_DESCRIPTIVE_AGENT_CLIENT_SECRET: str = ""
    QUESTION_GEN_MCQ_AGENT_CLIENT_ID: str = ""
    QUESTION_GEN_MCQ_AGENT_CLIENT_SECRET: str = ""
    QUESTION_GEN_CODING_AGENT_CLIENT_ID: str = ""
    QUESTION_GEN_CODING_AGENT_CLIENT_SECRET: str = ""
    EVALUATION_DESCRIPTIVE_AGENT_CLIENT_ID: str = ""
    EVALUATION_DESCRIPTIVE_AGENT_CLIENT_SECRET: str = ""

    # Resume upload
    MAX_RESUME_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Code execution sandbox for CODING questions
    CODE_EXECUTION_TIMEOUT_SECONDS: float = 5.0
    CODE_EXECUTION_MAX_OUTPUT_CHARS: int = 4000

    # --- voice-agent-service: AI outbound phone screens (app/services/voice_agent_client.py) ---
    # Same pattern as agent-builder-service above: this service's own IAM-issued, resource-bound
    # Service Principal credential (client_id/client_secret), exchanged for a short-lived access
    # token via iam-service's POST /auth/token (reuses app.core.iam_client.agent_token_cache),
    # instead of a per-user token - the recruiter's own token never leaves the browser for this.
    VOICE_AGENT_SERVICE_URL: str = "http://localhost:8004"
    VOICE_AGENT_CLIENT_ID: str = ""
    VOICE_AGENT_CLIENT_SECRET: str = ""

    # Shared secret embedded as a query param in the webhook_url handed to voice-agent-service at
    # call-creation time (see app/api/webhooks.py) - the only way that inbound POST authenticates
    # itself back to us, since it isn't a normal IAM-bearer-token caller.
    VOICE_AGENT_WEBHOOK_SECRET: str = ""

    # This service's own publicly-reachable base URL, used to build the webhook_url above. Local
    # dev without a tunnel (e.g. ngrok) means voice-agent-service can never actually reach this
    # path - see .env.example for the same caveat voice-agent-service documents for its own
    # Twilio tunnel requirement. Everything else (triggering a call, polling call status) still
    # works without a tunnel.
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # --- one-time use: scripts/bootstrap_voice_agent_identity.py only ---
    IAM_BOOTSTRAP_ADMIN_EMAIL: str = "admin@talentos-platform.com"
    IAM_BOOTSTRAP_ADMIN_PASSWORD: str = "change-me-local-dev-password"


@lru_cache
def get_settings() -> Settings:
    return Settings()
