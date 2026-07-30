from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RahulGPT Job Search"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://rahulgpt:rahulgpt_local@localhost:5432/rahulgpt"
    ai_provider: str = "auto"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-sol"
    connectsafely_api_key: str | None = None
    connectsafely_base_url: str = "https://api.connectsafely.ai"
    connectsafely_account_id: str | None = None
    discovery_run_hour: int = Field(default=8, ge=0, le=23)
    discovery_timezone: str = "Asia/Kolkata"
    ats_ca_bundle: str | None = None
    outbound_ca_bundle: str | None = None
    outreach_daily_send_limit: int = Field(default=100, ge=1, le=500)
    backend_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
