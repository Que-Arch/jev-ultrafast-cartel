import json

import pytest

from jev_ultrafast.model_provider import (
    build_request,
    normalize_response,
    provider_config,
)


def test_typesafe_is_the_default_provider(monkeypatch):
    monkeypatch.delenv("JEV_DECISION_PROVIDER", raising=False)
    monkeypatch.delenv("JEV_DECISION_BASE_URL", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-typesafe-key")
    config = provider_config()
    assert config.provider == "typesafe"
    assert config.url == "https://api.typesafe.ai/v1/systemone"


def test_openai_compatible_provider_builds_chat_request(monkeypatch):
    monkeypatch.setenv("JEV_DECISION_PROVIDER", "openai-compatible")
    monkeypatch.setenv("JEV_DECISION_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("JEV_DECISION_MODEL", "cartel-browser-model")
    monkeypatch.setenv("JEV_DECISION_API_KEY", "test-provider-key")
    config = provider_config()
    request = build_request(config, {"state": {"url": "https://example.test"}})
    assert config.url == "https://api.example.test/v1/chat/completions"
    assert request["model"] == "cartel-browser-model"
    assert request["response_format"] == {"type": "json_object"}
    assert request["messages"][0]["role"] == "system"
    assert json.loads(request["messages"][1]["content"])["state"]["url"] == "https://example.test"


def test_openai_compatible_response_is_normalized():
    payload = {"choices": [{"message": {"content": '{"answers": {"operation": {"choice": "DONE"}}}'}}]}
    assert normalize_response("openai-compatible", payload) == {"answers": {"operation": {"choice": "DONE"}}}


def test_missing_provider_key_fails_closed(monkeypatch):
    monkeypatch.setenv("JEV_DECISION_PROVIDER", "openai-compatible")
    monkeypatch.delenv("JEV_DECISION_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="decision provider API key"):
        provider_config()
