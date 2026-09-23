"""Configurable decision-provider adapter for Jev."""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    url: str
    api_key: str
    model: str


def provider_config() -> ProviderConfig:
    provider = os.environ.get("JEV_DECISION_PROVIDER", "typesafe").strip().lower()
    if provider not in {"typesafe", "openai-compatible", "codex-cli"}:
        raise RuntimeError("Unsupported Jev decision provider; no action executed.")
    key = os.environ.get("JEV_DECISION_API_KEY", "").strip()
    if provider == "typesafe" and not key:
        key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if provider != "codex-cli" and not key:
        raise RuntimeError("Jev decision provider API key is missing; no action executed.")
    if provider == "typesafe":
        url = os.environ.get("JEV_DECISION_BASE_URL", "https://api.typesafe.ai/v1/systemone").rstrip("/")
        model = os.environ.get("TYPESAFE_MODEL", "jev-latest")
    elif provider == "openai-compatible":
        base = os.environ.get("JEV_DECISION_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        model = os.environ.get("JEV_DECISION_MODEL", "gpt-4o-mini")
    else:
        url = "codex://subscription"
        model = os.environ.get("CODEX_MODEL", "subscription-default")
    return ProviderConfig(provider=provider, url=url, api_key=key, model=model)


def build_request(config: ProviderConfig, body: dict) -> dict:
    if config.provider == "typesafe":
        return {**body, "model": config.model}
    if config.provider == "codex-cli":
        return body
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
    if provider in {"typesafe", "codex-cli"}:
        return payload
    try:
        content = payload["choices"][0]["message"]["content"]
        result = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Decision provider returned invalid JSON; no action executed.") from exc
    if not isinstance(result, dict) or "answers" not in result:
        raise RuntimeError("Decision provider returned no Jev answers; no action executed.")
    return result


def _parse_codex_json(text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("Codex returned invalid Jev JSON; no action executed.") from None
        try:
            result = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Codex returned invalid Jev JSON; no action executed.") from exc
    if not isinstance(result, dict) or "answers" not in result:
        raise RuntimeError("Codex returned no Jev answers; no action executed.")
    return result


def request_decision(config: ProviderConfig, body: dict, http_post) -> dict:
    if config.provider != "codex-cli":
        return normalize_response(config.provider, http_post(config.url, config.api_key, build_request(config, body)))
    codex_body = json.loads(json.dumps(body))
    page = codex_body.get("state", {}).get("page", {})
    if isinstance(page.get("text"), str):
        page["text"] = page["text"][:6000]
    prompt = (
        "You are the decision engine inside Jev. Do not use tools and do not browse. "
        "Return JSON only with an `answers` object matching the questions in the supplied state. "
        "For every choice answer, include exactly: choice, probabilities, confidence. "
        "probabilities must contain every candidate ID exactly once, use numbers from 0 to 1, "
        "sum to 1, and make the selected choice the highest probability. confidence must be "
        "number from 0 to 1. If the goal says to finish when the page is observed and the page "
        "is already observed, choose DONE immediately. Choose only an observed operation and "
        "observed target. Never invent selectors, coordinates, URLs, shell commands or code. "
        "This output will be validated before any browser action.\n\n"
        + json.dumps(codex_body)
    )
    with tempfile.TemporaryDirectory(prefix="jev-codex-") as directory:
        output = Path(directory) / "last-message.json"
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--output-last-message",
            str(output),
            prompt,
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("Codex subscription unavailable; no action executed.") from exc
        if completed.returncode != 0 or not output.exists():
            raise RuntimeError("Codex subscription returned no decision; no action executed.")
        return _parse_codex_json(output.read_text(encoding="utf-8"))
