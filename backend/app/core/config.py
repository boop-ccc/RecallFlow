from pathlib import Path

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


BACKEND_DIR = (
    Path(__file__).resolve().parents[2]
)

DATABASE_FILE = (
    BACKEND_DIR / "recallflow.db"
)


class Settings(BaseSettings):
    """
    RecallFlow 统一配置中心。

    Local:
        默认 SQLite，开箱即用。

    Docker / Production-like:
        通过 DATABASE_URL 切换 PostgreSQL，
        上层 Repository / Service 不需要修改。
    """

    # ---------- Application ----------
    app_name: str = "RecallFlow MA"
    app_env: str = "dev"

    # ---------- Database ----------
    database_url: str = (
        "sqlite+aiosqlite:///"
        f"{DATABASE_FILE.as_posix()}"
    )

    sql_echo: bool = False

    # ---------- LLM / Groq ----------
    llm_api_key: str = Field(
        default="",
        validation_alias="GROQ_API_KEY",
    )

    llm_model: str = Field(
        default="qwen/qwen3.8-27b",
        validation_alias="GROQ_MODEL",
    )

    llm_base_url: str = (
        "https://api.groq.com/openai/v1"
    )

    llm_timeout_seconds: float = 30.0

    # ---------- Settings ----------
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
