"""Settings for Alpha Brain."""

from pydantic import Field, HttpUrl, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database settings
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URL",
        examples=["postgresql://user:pass@localhost:5432/dbname"],
    )

    # Ollama settings (optional)
    openai_base_url: HttpUrl | None = Field(
        None,
        description="Ollama API base URL for entity extraction",
        examples=["http://localhost:11434/v1"],
    )
    openai_api_key: str | None = Field(
        default="not-needed", description="API key (not needed for Ollama)"
    )

    # Model settings
    ollama_model: str = Field(
        default="llama3.2:3b", description="Ollama model to use for entity extraction"
    )

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=9100, description="Server port")

    @property
    def async_database_url(self) -> str:
        """Convert the database URL to async format."""
        url = str(self.database_url)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
