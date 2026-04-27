from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # Database (asyncpg URL for SQLAlchemy)
    DATABASE_URL: str = ""

    # LLM providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # External services
    GOOGLE_PLACES_API_KEY: str = ""

    # Security
    ADMIN_TOKEN: str = ""
    INTERNAL_TOKEN: str = ""

    # Storage
    STORAGE_BUCKET: str = "prepai-photos"

    # Rate limiting
    RATE_LIMIT_MAX_REQUESTS: int = 1000
    RATE_LIMIT_WINDOW_HOURS: int = 24

    # AI cost cap
    AI_COST_CAP_USD: float = 5.0

    # CORS (comma-separated origins)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8081"

    # Sentry
    SENTRY_DSN: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
