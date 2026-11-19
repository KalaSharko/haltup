"""Configuration serveur lue dans les variables d'environnement (et un fichier .env local facultatif).

Aucune clé n'est jamais envoyée au navigateur.
"""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path: str) -> None:
    """Lecteur minimal de .env (KEY=VALUE). Les variables déjà définies sont prioritaires."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv(os.path.join(ROOT, ".env"))


class Settings:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    # none | anthropic | openai_compatible
    ai_provider = os.environ.get("AI_PROVIDER", "none").strip().lower()
    ai_model = os.environ.get("AI_MODEL", "").strip()
    ai_effort = os.environ.get("AI_EFFORT", "low").strip()
    ai_timeout = float(os.environ.get("AI_TIMEOUT_SECONDS", "30"))
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    ai_api_key = os.environ.get("AI_API_KEY", "").strip()
    ai_base_url = os.environ.get("AI_BASE_URL", "").strip().rstrip("/")


settings = Settings()
