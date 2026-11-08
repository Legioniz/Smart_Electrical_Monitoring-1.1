from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

from .paths import ROOT
load_dotenv(ROOT / ".env")


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in os.getenv(name, default).split(",") if part.strip())


APP_PORT = int(os.getenv("APP_PORT", "8000"))


@dataclass(frozen=True)
class Settings:
    app_name: str = "Smart Meter Explorer"
    app_env: str = os.getenv("APP_ENV", "development")
    app_secret_key: str = os.getenv("APP_SECRET_KEY", "")
    app_port: int = APP_PORT
    app_origins: tuple[str, ...] = _csv(
        "APP_ALLOWED_ORIGINS",
        f"http://127.0.0.1:{APP_PORT},http://localhost:{APP_PORT},http://[::1]:{APP_PORT}",
    )
    app_hosts: tuple[str, ...] = _csv(
        "APP_ALLOWED_HOSTS", f"127.0.0.1:{APP_PORT},localhost:{APP_PORT},[::1]:{APP_PORT}"
    )
    database_url: str = os.getenv("DATABASE_URL", "")
    migration_database_url: str = os.getenv("MIGRATION_DATABASE_URL", "")
    session_cookie: str = "sme_session"
    preauth_cookie: str = "sme_preauth"
    customer_idle_minutes: int = 20
    admin_idle_minutes: int = 10
    customer_absolute_hours: int = 4
    admin_absolute_hours: int = 2
    max_body_bytes: int = 1_048_576
    request_rate_per_minute: int = 120
    login_attempts_per_10m: int = 8
    local_llm_enabled: bool = os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true"
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "")
    ollama_model_sha256: str = os.getenv("OLLAMA_MODEL_SHA256", "")
    ollama_models_dir: str = (os.getenv("OLLAMA_MODELS_DIR") or os.getenv("OLLAMA_MODELS") or os.path.join(os.path.expanduser("~"), ".ollama", "models"))
    seed: int = int(os.getenv("DEMO_SEED", "20261031"))
    demo_customer_username: str = os.getenv("DEMO_CUSTOMER_USERNAME", "demo.customer")


settings = Settings()


def validate_settings() -> None:
    if settings.app_env == "production" and len(settings.app_secret_key) < 48:
        raise RuntimeError("APP_SECRET_KEY must contain at least 48 characters in production.")
    if not settings.app_secret_key and settings.app_env != "test":
        raise RuntimeError(
            "APP_SECRET_KEY is missing. Run `python scripts/create_env.py` and configure .env."
        )
    if settings.database_url and not settings.database_url.startswith("mysql+mysqlconnector://"):
        if not (settings.app_env == "test" and settings.database_url.startswith("sqlite://")):
            raise RuntimeError("DATABASE_URL must use the local MySQL mysql+mysqlconnector driver.")
