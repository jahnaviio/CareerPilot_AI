"""Concrete providers. All HTTP via requests so no vendor SDK is required.
Provider-specific logic lives only here."""
from __future__ import annotations

import requests

from config import Settings, settings
from core.llm.base import LLMError, LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, cfg: Settings):
        if not cfg.llm_model:
            raise LLMError("LLM_MODEL is not set (e.g. llama3.2) for the Ollama provider.")
        self.cfg = cfg

    def complete(self, system, prompt, *, max_tokens=None, temperature=0.2):
        try:
            r = requests.post(
                f"{self.cfg.ollama_host.rstrip('/')}/api/chat",
                json={"model": self.cfg.llm_model, "stream": False,
                      "options": {"temperature": temperature, "num_predict": max_tokens or self.cfg.llm_max_tokens},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
                timeout=self.cfg.llm_timeout_s)
            r.raise_for_status()
            return r.json()["message"]["content"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise LLMError(f"Ollama request failed at {self.cfg.ollama_host}: {type(exc).__name__}") from exc


class OpenAICompatibleProvider(LLMProvider):
    """Any hosted service exposing POST {base}/chat/completions (Groq, OpenRouter, Together, OpenAI, vLLM...)."""
    name = "openai_compatible"

    def __init__(self, cfg: Settings):
        if not (cfg.llm_base_url and cfg.llm_api_key and cfg.llm_model):
            raise LLMError("Hosted LLM needs LLM_BASE_URL, LLM_API_KEY and LLM_MODEL.")
        self.cfg = cfg

    def complete(self, system, prompt, *, max_tokens=None, temperature=0.2):
        try:
            r = requests.post(
                f"{self.cfg.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.cfg.llm_api_key}"},
                json={"model": self.cfg.llm_model, "temperature": temperature,
                      "max_tokens": max_tokens or self.cfg.llm_max_tokens,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
                timeout=self.cfg.llm_timeout_s)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"Hosted LLM request failed: {type(exc).__name__}") from exc  # never echo the key


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, cfg: Settings):
        if not (cfg.llm_api_key and cfg.llm_model):
            raise LLMError("Anthropic provider needs LLM_API_KEY and LLM_MODEL.")
        self.cfg = cfg

    def complete(self, system, prompt, *, max_tokens=None, temperature=0.2):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self.cfg.llm_api_key, "anthropic-version": "2023-06-01"},
                json={"model": self.cfg.llm_model, "max_tokens": max_tokens or self.cfg.llm_max_tokens,
                      "temperature": temperature, "system": system,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=self.cfg.llm_timeout_s)
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise LLMError(f"Anthropic request failed: {type(exc).__name__}") from exc


def get_provider(cfg: Settings = settings) -> LLMProvider | None:
    """Returns the configured provider, or None when LLM_PROVIDER=none.
    Raises LLMError for a misconfigured provider so the UI can explain what is missing."""
    p = cfg.llm_provider
    if p in ("", "none"):
        return None
    table = {"ollama": OllamaProvider, "openai_compatible": OpenAICompatibleProvider, "anthropic": AnthropicProvider}
    if p not in table:
        raise LLMError(f"Unknown LLM_PROVIDER '{p}'. Use none, ollama, openai_compatible or anthropic.")
    return table[p](cfg)


def llm_status(cfg: Settings = settings) -> tuple[bool, str]:
    """(available, human message) without making a network call."""
    try:
        prov = get_provider(cfg)
    except LLMError as exc:
        return False, str(exc)
    if prov is None:
        return False, "No LLM configured. Deterministic analysis is active; AI-written text is disabled."
    return True, f"{prov.name} · {cfg.llm_model}"
