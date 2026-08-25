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


@lru_cache
def get_settings() -> Settings:
    return Settings()
