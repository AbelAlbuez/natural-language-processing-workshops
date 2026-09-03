"""Configuración del servicio. Nada de esto se hardcodea en la lógica (§20)."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Base de datos ────────────────────────────────────────────────────────
    db_user: str = "news_corpus"
    db_password: str = "news_corpus"
    db_name: str = "news_corpus"
    db_host: str = "localhost"
    db_port: int = 5433

    # ── Configuración externa ────────────────────────────────────────────────
    config_dir: Path = Path("config")

    # ── Horizonte del corpus ─────────────────────────────────────────────────
    corpus_start: date = date(2006, 8, 7)
    corpus_end: date = date(2026, 8, 7)
    enabled_providers: str = "sitemap"

    # ── Red ──────────────────────────────────────────────────────────────────
    request_timeout_sec: int = 45
    max_retries: int = 5
    user_agent: str = "news-corpus-research/0.1 (proyecto academico NLP)"

    # ── Rate limiting por proveedor (req/s) ──────────────────────────────────
    rate_sitemap: float = 1.0
    # 0.04 req/s = 1 cada 25 s. Medido en Fase 1: a ese ritmo GDELT respondió
    # el 38% de las consultas. Subirlo empeora la tasa de éxito.
    rate_gdelt: float = 0.04
    rate_common_crawl: float = 0.2
    rate_wayback: float = 0.2

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "console"

    @field_validator("config_dir", mode="after")
    @classmethod
    def _resolve_config_dir(cls, v: Path) -> Path:
        return v if v.is_absolute() else (REPO_ROOT / v)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def providers(self) -> set[str]:
        return {p.strip() for p in self.enabled_providers.split(",") if p.strip()}

    def rate_for(self, provider: str) -> float:
        """Rate limit del proveedor; cae a un valor conservador si no se conoce."""
        return getattr(self, f"rate_{provider}", 0.2)


@lru_cache
def get_settings() -> Settings:
    return Settings()
