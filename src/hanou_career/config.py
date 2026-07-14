"""Paths and settings for hanou-career."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Package lives at src/hanou_career → repo root is parents[2]
PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hano_database_url: str = "postgresql+psycopg://hano:hano@localhost:5432/hano"
    hanou_online_max_pages: int = 3
    hanou_top_n: int = 100
    hanou_region: str = "Niedersachsen"
    hanou_serve_host: str = "127.0.0.1"
    hanou_serve_port: int = 8765
    hanou_jsonl_limit: int = 5000
    hanou_max_age_days: int = 90
    hanou_verify_urls: bool = True
    hanou_skip_stale_jsonl: bool = True
    # Arbeitsagentur search currently returns many gone (410) links — off by default.
    hanou_include_arbeitsagentur: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
