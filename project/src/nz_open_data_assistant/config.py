from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NZ Regional Insights Assistant"
    database_path: Path = Path("runtime/app.db")
    catalogue_base_url: str = "https://catalogue.data.govt.nz"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    api_url: str = "http://localhost:8000"
    request_timeout_seconds: float = 20.0
    max_search_results: int = 5
    enable_data_tools: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
