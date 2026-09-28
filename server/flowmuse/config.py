from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOWMUSE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/flowmuse.db"
    provider_base_url: str = "https://api.openai.com/v1"
    provider_api_key: SecretStr = SecretStr("")
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "[::1]"]
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173",
                               "http://localhost:8000", "http://127.0.0.1:8000"]
    request_timeout: float = Field(120, gt=0, le=600)
    run_timeout: float = Field(900, gt=0, le=3600)
    max_output_tokens: int = Field(2048, ge=1, le=32768)
    max_concurrent_runs: int = Field(2, ge=1, le=16)
    max_pending_runs: int = Field(16, ge=1, le=128)
    max_request_bytes: int = Field(32 * 1024 * 1024, ge=1024)
    max_response_bytes: int = Field(64 * 1024 * 1024, ge=1024)
    static_dir: Path = Path(__file__).resolve().parents[2] / "web" / "dist"
