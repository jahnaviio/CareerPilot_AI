"""
Pluggable LLM provider for CareerPilot AI.

Every agent that needs free-text generation (resume matching commentary,
resume tailoring, cover letters) calls `generate_text()` from this module
instead of importing `ollama` or `anthropic` directly. The active backend
is chosen by LLM_PROVIDER in the environment (see config.py):

    LLM_PROVIDER=claude  -> Anthropic API (requires ANTHROPIC_API_KEY)
    LLM_PROVIDER=ollama   -> local Ollama server (requires `ollama serve`)
    LLM_PROVIDER=none     -> no LLM; callers get LLMUnavailableError and
                             should fall back to deterministic logic

This means the app *runs* with zero AI configuration (rule-based matching
still works), and upgrades to full AI features the moment a provider is
configured — no code changes required, just an env var.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from config import llm_config

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """Raised when no LLM backend is configured or the backend call fails."""


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str


def generate_text(prompt: str, system: str | None = None, max_tokens: int | None = None) -> LLMResponse:
    """
    Generate text from the configured LLM provider.

    Raises LLMUnavailableError if no provider is configured or the call
    fails — callers are expected to catch this and fall back to
    deterministic/template behavior so the product never hard-crashes
    just because an API key or local model isn't available.
    """
    provider = llm_config.provider

    if provider == "claude":
        return _generate_claude(prompt, system, max_tokens)
    if provider == "ollama":
        return _generate_ollama(prompt, system)

    raise LLMUnavailableError(
        "No LLM provider configured. Set LLM_PROVIDER=claude (with "
        "ANTHROPIC_API_KEY) or LLM_PROVIDER=ollama in your .env file."
    )


def _generate_claude(prompt: str, system: str | None, max_tokens: int | None) -> LLMResponse:
    if not llm_config.anthropic_api_key:
        raise LLMUnavailableError(
            "LLM_PROVIDER=claude but ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file."
        )
    try:
        import anthropic
    except ImportError as exc:
        raise LLMUnavailableError(
            "The 'anthropic' package is not installed. Run: pip install anthropic"
        ) from exc

    try:
        client = anthropic.Anthropic(api_key=llm_config.anthropic_api_key)
        kwargs = {}
        if system:
            kwargs["system"] = system
        response = client.messages.create(
            model=llm_config.anthropic_model,
            max_tokens=max_tokens or llm_config.anthropic_max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(text=text, provider="claude", model=llm_config.anthropic_model)
    except Exception as exc:
        logger.exception("Claude API call failed")
        raise LLMUnavailableError(f"Claude API call failed: {exc}") from exc


def _generate_ollama(prompt: str, system: str | None) -> LLMResponse:
    try:
        from ollama import Client
    except ImportError as exc:
        raise LLMUnavailableError(
            "The 'ollama' package is not installed. Run: pip install ollama"
        ) from exc

    try:
        client = Client(host=llm_config.ollama_host)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat(model=llm_config.ollama_model, messages=messages)
        text = response["message"]["content"]
        return LLMResponse(text=text, provider="ollama", model=llm_config.ollama_model)
    except Exception as exc:
        logger.exception("Ollama call failed")
        raise LLMUnavailableError(
            f"Could not reach Ollama at {llm_config.ollama_host}. "
            f"Is 'ollama serve' running? ({exc})"
        ) from exc


def is_llm_available() -> bool:
    """Cheap configuration check (does not make a network call)."""
    return llm_config.is_configured
