"""Appel facultatif à un modèle d'IA, avec fournisseur configurable.

- AI_PROVIDER=none (défaut) : mode démonstration, aucun appel externe.
- AI_PROVIDER=anthropic : Claude API via le SDK officiel `anthropic` (pip install -r requirements-ai.txt).
- AI_PROVIDER=openai_compatible : tout service exposant /chat/completions (AI_BASE_URL + AI_API_KEY).

La réponse du modèle est toujours validée côté serveur (voir assistant.py) ; en cas d'échec,
l'application revient au moteur de règles sans casser l'interface.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .config import settings

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
# Modèles acceptant le repli serveur automatique en cas de refus (paramètre `fallbacks`).
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-fable-5-2"}


class AIError(Exception):
    pass


def _anthropic_module():
    try:
        import anthropic  # noqa: WPS433 (import facultatif)
        return anthropic
    except ImportError:
        return None


def status() -> dict:
    p = settings.ai_provider
    if p == "anthropic":
        if not settings.anthropic_api_key:
            return {"mode": "demo", "reason": "AI_PROVIDER=anthropic mais ANTHROPIC_API_KEY est vide."}
        if _anthropic_module() is None:
            return {"mode": "demo", "reason": "Le paquet Python « anthropic » n'est pas installé (pip install -r requirements-ai.txt)."}
        return {"mode": "ai", "provider": "Anthropic (Claude API)", "model": settings.ai_model or DEFAULT_ANTHROPIC_MODEL}
    if p == "openai_compatible":
        if not (settings.ai_base_url and settings.ai_model):
            return {"mode": "demo", "reason": "AI_BASE_URL et AI_MODEL sont requis pour un fournisseur compatible."}
        host = re.sub(r"^https?://", "", settings.ai_base_url).split("/")[0]
        return {"mode": "ai", "provider": "Service compatible (%s)" % host, "model": settings.ai_model}
    return {"mode": "demo", "reason": "Aucun fournisseur d'IA configuré (AI_PROVIDER=none)."}


def _call_anthropic(system: str, user: str) -> str:
    anthropic = _anthropic_module()
    model = settings.ai_model or DEFAULT_ANTHROPIC_MODEL
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=settings.ai_timeout, max_retries=1)
    extra_body = {}
    betas = []
    if settings.ai_effort:
        extra_body["output_config"] = {"effort": settings.ai_effort}
    if model in _FALLBACK_MODELS:
        betas.append("server-side-fallback-2026-07-01")
        extra_body["fallbacks"] = "default"
    kwargs = {"model": model, "max_tokens": 4000, "system": system,
              "messages": [{"role": "user", "content": user}]}
    if betas:
        kwargs["betas"] = betas
    if extra_body:
        kwargs["extra_body"] = extra_body
    try:
        response = client.beta.messages.create(**kwargs)
    except anthropic.RateLimitError as exc:
        raise AIError("limite de requêtes atteinte") from exc
    except anthropic.APIStatusError as exc:
        raise AIError("erreur du service (HTTP %s)" % exc.status_code) from exc
    except anthropic.APIConnectionError as exc:
        raise AIError("connexion impossible au service") from exc
    if response.stop_reason == "refusal":
        raise AIError("le modèle a refusé de répondre")
    if response.stop_reason == "max_tokens":
        raise AIError("réponse tronquée")
    return "".join(getattr(b, "text", "") for b in response.content if b.type == "text")


def _call_openai_compatible(system: str, user: str) -> str:
    body = json.dumps({
        "model": settings.ai_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = "Bearer " + settings.ai_api_key
    req = urllib.request.Request(settings.ai_base_url + "/chat/completions", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=settings.ai_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AIError("erreur du service (HTTP %s)" % exc.code) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise AIError("connexion impossible au service") from exc
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise AIError("format de réponse inattendu") from exc


def complete_json(system: str, user: str) -> dict:
    """Appelle le fournisseur configuré et renvoie l'objet JSON extrait de la réponse."""
    st = status()
    if st["mode"] != "ai":
        raise AIError(st["reason"])
    if settings.ai_provider == "anthropic":
        text = _call_anthropic(system, user)
    else:
        text = _call_openai_compatible(system, user)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise AIError("réponse sans JSON")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError as exc:
        raise AIError("JSON invalide") from exc
    if not isinstance(data, dict):
        raise AIError("JSON inattendu")
    return data
