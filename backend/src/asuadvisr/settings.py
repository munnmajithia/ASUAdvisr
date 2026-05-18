"""Environment-backed settings, loaded via pydantic-settings.

Reads from the repo-root `.env` file and the process environment. Tests can
override values by passing kwargs to `Settings(...)` directly.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    supabase_url: str = Field(default="")
    supabase_anon_key: str = Field(default="")
    supabase_service_role_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")

    model_config = SettingsConfigDict(
        env_file=_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


def get_settings() -> Settings:
    return Settings()
