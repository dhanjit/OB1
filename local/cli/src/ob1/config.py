import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    embed_model: str
    embed_dim: int
    ollama_url: str
    metadata_provider: str
    metadata_model: str | None
    anthropic_api_key: str | None
    openai_api_key: str | None
    google_api_key: str | None

    @property
    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password}"
        )


def load() -> Config:
    return Config(
        db_host=os.environ.get("OB1_DB_HOST", "127.0.0.1"),
        db_port=int(os.environ.get("OB1_DB_PORT", "5433")),
        db_name=os.environ.get("OB1_DB_NAME", "openbrain"),
        db_user=os.environ.get("OB1_DB_USER", "openbrain"),
        db_password=os.environ.get("OB1_DB_PASSWORD", "openbrain"),
        embed_model=os.environ.get("OB1_EMBED_MODEL", "nomic-embed-text"),
        embed_dim=int(os.environ.get("OB1_EMBED_DIM", "768")),
        ollama_url=os.environ.get("OB1_OLLAMA_URL", "http://127.0.0.1:11434"),
        metadata_provider=os.environ.get("OB1_METADATA_PROVIDER", "none").lower(),
        metadata_model=os.environ.get("OB1_METADATA_MODEL") or None,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        google_api_key=os.environ.get("GOOGLE_API_KEY") or None,
    )
