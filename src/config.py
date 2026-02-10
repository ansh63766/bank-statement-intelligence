import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Server configuration
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # LLM Provider configuration (openrouter, openai, deepinfra, google)
    LLM_PROVIDER: str = Field(default="openrouter")

    # API Keys & Models
    OPENROUTER_API_KEY: Optional[str] = Field(default=None)
    OPENROUTER_MODEL: str = Field(default="google/gemini-2.5-flash:free")

    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")

    DEEPINFRA_API_KEY: Optional[str] = Field(default=None)
    DEEPINFRA_MODEL: str = Field(default="meta-llama/Meta-Llama-3-8B-Instruct")

    GOOGLE_API_KEY: Optional[str] = Field(default=None)
    GOOGLE_MODEL: str = Field(default="gemini-2.5-flash")

    # App settings
    DEBUG: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
