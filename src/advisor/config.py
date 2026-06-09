"""Centralized settings, sourced from environment / .env file."""
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    hf_token: str = Field(default="", alias="HF_TOKEN")
    alpha_vantage_key: str = Field(default="demo", alias="ALPHA_VANTAGE_KEY")

    llm_model_id: str = Field(default="meta-llama/Llama-3.1-8B-Instruct", alias="LLM_MODEL_ID")
    llm_provider: str = Field(default="together", alias="LLM_PROVIDER")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=1024, alias="LLM_MAX_TOKENS")

    embed_model_id: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBED_MODEL_ID")
    chroma_dir: str = Field(default="./data/chroma", alias="CHROMA_DIR")

    @property
    def chroma_path(self) -> Path:
        return Path(self.chroma_dir).resolve()


settings = Settings()
