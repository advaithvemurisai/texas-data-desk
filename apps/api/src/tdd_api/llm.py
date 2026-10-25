"""One OpenAI-compatible chat client for every free-tier provider (CLAUDE.md rule 1).

Switching models is a config change: a model is named "<provider>:<model id>", e.g.
"gemini:gemini-3.8-flash" or "groq:openai/gpt-oss-120b". Only free tiers are listed here.
"""

import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    key_env: str


PROVIDERS = {
    p.name: p
    for p in [
        Provider(
            "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"
        ),
        Provider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY"),
        Provider("cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
        Provider("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    ]
}


# A 429 for a per-day limit will not clear by waiting minutes. Gemini names the quota
# (..._PerDay...), Groq says "requests per day (RPD)" / "tokens per day (TPD)".
DAILY_QUOTA = re.compile(r"PerDay|per day|\bRPD\b|\bTPD\b", re.IGNORECASE)


# Provider errors name the account (Groq: org_...); results files are committed, so drop it.
ACCOUNT_ID = re.compile(r"org_[A-Za-z0-9]{10,}")


def _snippet(text: str, limit: int = 300) -> str:
    return ACCOUNT_ID.sub("org_<redacted>", text)[:limit]


class QuotaExhaustedError(RuntimeError):
    """The provider kept answering 429 after every retry (likely the daily free quota)."""


@dataclass(frozen=True)
class ModelRef:
    provider: Provider
    model: str

    @classmethod
    def parse(cls, ref: str) -> "ModelRef":
        name, sep, model = ref.partition(":")
        if not sep or name not in PROVIDERS or not model:
            known = ", ".join(PROVIDERS)
            raise ValueError(f"model must be <provider>:<model id> with provider in {known}")
        if name == "openrouter" and not model.endswith(":free"):
            raise ValueError("OpenRouter models must be :free variants (CLAUDE.md rule 1)")
        return cls(PROVIDERS[name], model)

    def __str__(self) -> str:
        return f"{self.provider.name}:{self.model}"


@dataclass
class Usage:
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0  # includes hidden reasoning tokens where the provider counts them
    rate_limited: int = 0  # 429 responses
    seconds: float = 0.0  # time spent waiting on the provider, excluding backoff

    def add(self, usage: dict[str, Any] | None) -> None:
        self.requests += 1
        usage = usage or {}
        self.prompt_tokens += usage.get("prompt_tokens") or 0
        self.completion_tokens += usage.get("completion_tokens") or 0
        self.total_tokens += usage.get("total_tokens") or 0


def _retry_wait(response: httpx.Response, attempt: int, base_wait: float) -> float:
    """Seconds to wait before retrying: provider hints first, then exponential backoff."""
    if after := response.headers.get("retry-after"):
        try:
            return float(after)
        except ValueError:
            pass
    # Gemini puts it in the body: "retryDelay": "37s".
    if match := re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', response.text):
        return float(match[1])
    return base_wait * 2**attempt


@dataclass
class ChatClient:
    ref: ModelRef
    timeout: float = 120.0
    max_attempts: int = 6
    base_wait: float = 2.0
    max_wait: float = 90.0
    sleep: Callable[[float], None] = time.sleep
    usage: Usage = field(default_factory=Usage)
    transport: httpx.BaseTransport | None = None

    def __post_init__(self) -> None:
        key = os.environ.get(self.ref.provider.key_env)
        if not key:
            raise RuntimeError(f"{self.ref.provider.key_env} is not set (see .env.example)")
        self._http = httpx.Client(
            base_url=self.ref.provider.base_url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=self.timeout,
            transport=self.transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "ChatClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """One chat completion; returns the first choice's message."""
        body: dict[str, Any] = {"model": self.ref.model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        response: httpx.Response | None = None
        for attempt in range(self.max_attempts):
            if response is not None:  # back off before every retry, not after the last try
                wait = min(_retry_wait(response, attempt - 1, self.base_wait), self.max_wait)
                log.info("%s: HTTP %s, retrying in %.0fs", self.ref, response.status_code, wait)
                self.sleep(wait)
            started = time.monotonic()
            response = self._http.post("/chat/completions", json=body)
            self.usage.seconds += time.monotonic() - started
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable:
                response.raise_for_status()
                data = response.json()
                self.usage.add(data.get("usage"))
                return data["choices"][0]["message"]
            if response.status_code == 429:
                self.usage.rate_limited += 1
                log.info("%s: 429 body: %s", self.ref, _snippet(response.text, 600))
                if DAILY_QUOTA.search(response.text):
                    raise QuotaExhaustedError(
                        f"{self.ref}: daily quota used: {_snippet(response.text)}"
                    )
        assert response is not None
        if response.status_code == 429:
            raise QuotaExhaustedError(f"{self.ref}: still rate-limited: {_snippet(response.text)}")
        response.raise_for_status()
        raise AssertionError("unreachable")
