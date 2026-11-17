"""Common LLM provider interface + structured (Pydantic-validated) output helper."""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from core.security import UNTRUSTED_NOTICE

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Provider missing, unreachable, or returned unusable output."""


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, system: str, prompt: str, *, max_tokens: int | None = None, temperature: float = 0.2) -> str: ...

    def complete_json(self, schema: type[T], system: str, prompt: str, *, retries: int = 1) -> T:
        """Ask for JSON, validate with Pydantic, retry once with the validation error."""
        sys_full = f"{system}\n\n{UNTRUSTED_NOTICE}\nReturn ONLY one JSON object matching this JSON Schema, no prose, no markdown fences:\n{json.dumps(schema.model_json_schema())}"
        last_err = ""
        user = prompt
        for _ in range(retries + 1):
            raw = self.complete(sys_full, user, temperature=0.0)
            try:
                return schema.model_validate(json.loads(_extract_json(raw)))
            except (ValueError, ValidationError) as exc:
                last_err = str(exc)[:600]
                user = f"{prompt}\n\nYour previous reply was invalid ({last_err}). Return only valid JSON."
        raise LLMError(f"Model did not return valid structured output: {last_err}")


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return raw[start:end + 1]
