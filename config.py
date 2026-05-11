"""
config.py
Loads configuration from environment variables and .env file.

GEMINI_API_KEY resolution order:
  1. os.environ  (set by Colab notebook before launching Streamlit subprocess)
  2. .env file   (used when running locally)
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-flash"
    database_url: str = "sqlite:///./hr_agent.db"
    max_file_size_mb: int = 10
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # pydantic-settings reads os.environ automatically —
        # no custom resolver needed


@lru_cache()
def get_settings() -> Settings:
    return Settings()
