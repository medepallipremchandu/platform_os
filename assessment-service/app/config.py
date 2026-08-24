from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "TalentOS Assessment Service"
    ENV: str = "local"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    RELOAD: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # Security
    API_KEY: str = "change-me-local-dev-key"
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/talentos_assessment"

    # LLM providers
    LLM_PRIMARY_PROVIDER: str = "claude"
    LLM_FALLBACK_PROVIDER: str = "azure_openai"
    LLM_TIMEOUT_SECONDS: int = 60

    LLM_MAX_OUTPUT_TOKENS: int = 8192

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-5"

    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"
    AZURE_OPENAI_DEPLOYMENT: str = ""

    # Code execution sandbox for CODING questions
    CODE_EXECUTION_TIMEOUT_SECONDS: float = 5.0
    CODE_EXECUTION_MAX_OUTPUT_CHARS: int = 4000

    # intake-matching-service (service-to-service call to snapshot a submission's skills/rubrics)
    INTAKE_MATCHING_SERVICE_URL: str = "http://localhost:8000/api/v1"
    INTAKE_MATCHING_API_KEY: str = "change-me-local-dev-key"
    INTAKE_MATCHING_TIMEOUT_SECONDS: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
