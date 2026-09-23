"""Configurable decision-provider adapter for Jev."""

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    url: str
    api_key: str
    model: str


def provider_config() -> ProviderConfig:
    provider = os.environ.get("JEV_DECISION_PROVIDER", "typesafe").strip().lower()
    if provider not in {"typesafe", "openai-compatible"}:
        raise RuntimeError("Unsupported Jev decision provider; no action executed.")
    key = os.environ.get("JEV_DECISION_API_KEY", "").strip()
    if not key:
        key = os.environ.get("TYPESAFE_API_KEY", "").strip() if provider == "typesafe" else ""
    if not key:
        raise RuntimeError("Jev decision provider API key is missing; no action executed.")
    if provider == "typesafe":
        url = os.environ.get("JEV_DECISION_BASE_URL", "https://api.typesafe.ai/v1/systemone").rstrip("/")
        model = os.environ.get("TYPESAFE_MODEL", "jev-latest")
    else:
        base = os.environ.get("JEV_DECISION_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        model = os.environ.get("JEV_DECISION_MODEL", "gpt-4o-mini")
    return ProviderConfig(provider=provider, url=url, api_key=key, model=model)


def build_request(config: ProviderConfig, body: dict) -> dict:
    if config.provider == "typesafe":
        return {**body, "model": config.model}
    return {
        "model": config.model,
        "temperature": 0,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Jev's bounded browser decision engine. Return JSON only. "
                    "Return the same schema requested by the user. Choose only an observed "
                    "operation and observed target; never invent selectors, coordinates or code."
                ),
            },
            {"role": "user", "content": json.dumps(body)},
        ],
    }


def normalize_response(provider: str, payload: dict) -> dict:
    if provider == "typesafe":
        return payload
    try:
        content = payload["choices"][0]["message"]["content"]
        result = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Decision provider returned invalid JSON; no action executed.") from exc
    if not isinstance(result, dict) or "answers" not in result:
        raise RuntimeError("Decision provider returned no Jev answers; no action executed.")
    return result
