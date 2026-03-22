"""
config.py — Central configuration for the Figma → React Converter Agent.

Switch between OpenRouter and Ollama by changing LLM_PROVIDER in .env
No agent code changes needed.
"""

import os
from functools import lru_cache

import requests
from dotenv import load_dotenv

load_dotenv()

# ─── LLM Provider Selection ───────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").lower()

# ─── OpenRouter Settings ──────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.5:free")
OPENROUTER_MODEL_CANDIDATES = os.getenv(
    "OPENROUTER_MODEL_CANDIDATES",
    "minimax/minimax-m2.5:free,openrouter/auto",
)

# ─── Ollama Settings (future) ─────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# ─── Figma Settings ───────────────────────────────────────────────────────────
FIGMA_ACCESS_TOKEN = os.getenv("FIGMA_ACCESS_TOKEN", "")
FIGMA_BASE_URL = "https://api.figma.com/v1"
FIGMA_MAX_RETRIES = int(os.getenv("FIGMA_MAX_RETRIES", "5"))
FIGMA_RETRY_BASE_DELAY = float(os.getenv("FIGMA_RETRY_BASE_DELAY", "1.5"))
FIGMA_RETRY_MAX_DELAY = float(os.getenv("FIGMA_RETRY_MAX_DELAY", "20"))

# ─── Agent Settings ───────────────────────────────────────────────────────────
MAX_TOKENS = 8192
TEMPERATURE = 0.1       # Low temperature = more deterministic code generation
AGENT_RETRIES = 3       # Number of retries if an agent call fails


def _parse_model_candidates() -> list[str]:
    """Builds an ordered de-duplicated list of OpenRouter model candidates."""
    raw_candidates = [OPENROUTER_MODEL, *OPENROUTER_MODEL_CANDIDATES.split(",")]
    candidates: list[str] = []
    for model in raw_candidates:
        model = model.strip()
        if model and model not in candidates:
            candidates.append(model)
    return candidates


@lru_cache(maxsize=1)
def resolve_openrouter_model() -> tuple[str, str | None]:
    """
    Resolves the best OpenRouter model to use.

    If the configured model does not currently have an endpoint, falls back to
    the first available candidate and returns a warning string.
    """
    candidates = _parse_model_candidates()
    configured = OPENROUTER_MODEL

    if not OPENROUTER_API_KEY:
        return configured, None

    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        available = {
            item.get("id")
            for item in payload.get("data", [])
            if isinstance(item, dict) and item.get("id")
        }
    except requests.RequestException:
        # If model listing fails, keep user-configured model and defer to runtime.
        return configured, None

    for candidate in candidates:
        if candidate in available:
            if candidate != configured:
                return (
                    candidate,
                    f"Configured model '{configured}' is unavailable. Using '{candidate}' instead.",
                )
            return candidate, None

    if "openrouter/auto" in available:
        return (
            "openrouter/auto",
            f"Configured model '{configured}' is unavailable. Using 'openrouter/auto' instead.",
        )

    return configured, (
        f"Configured model '{configured}' was not found in OpenRouter model list. "
        "Attempting to use it anyway."
    )


def get_agno_model():
    """
    Returns the appropriate Agno model instance based on LLM_PROVIDER.
    Swap provider in .env with zero code changes.
    """
    if LLM_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY is not set. "
                "Add it to your .env file. Get one at https://openrouter.ai"
            )
        from agno.models.openrouter import OpenRouter
        resolved_model, _ = resolve_openrouter_model()
        return OpenRouter(
            id=resolved_model,
            api_key=OPENROUTER_API_KEY,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

    elif LLM_PROVIDER == "ollama":
        from agno.models.ollama import Ollama
        return Ollama(
            id=OLLAMA_MODEL,
            host=OLLAMA_BASE_URL,
            temperature=TEMPERATURE,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{LLM_PROVIDER}'. "
            "Must be 'openrouter' or 'ollama'."
        )


def validate_config():
    """Validates required config values are set and prints a summary."""
    errors = []

    if not FIGMA_ACCESS_TOKEN:
        errors.append("FIGMA_ACCESS_TOKEN is missing")

    if LLM_PROVIDER == "openrouter" and not OPENROUTER_API_KEY:
        errors.append("OPENROUTER_API_KEY is missing")

    if errors:
        raise EnvironmentError(
            "Configuration errors:\n" + "\n".join(f"  • {e}" for e in errors)
        )
