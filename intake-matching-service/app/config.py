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
    API_KEY: str = "change-me-local-dev-key"
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/talentos_intake_matching"

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

    # Resume upload
    MAX_RESUME_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB


@lru_cache
def get_settings() -> Settings:
    return Settings()
