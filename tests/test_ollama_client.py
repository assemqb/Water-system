"""Tests for Ollama HTTP client."""

from __future__ import annotations

from unittest.mock import patch

from analytics import ollama_client


def test_resolve_model_prefers_env_match():
    ollama_client.reset_cache()
    with patch.object(ollama_client, "list_models", return_value=["llama3.2:latest", "mistral:7b"]):
        with patch.dict("os.environ", {"OLLAMA_MODEL": "mistral"}):
            assert ollama_client.resolve_model() == "mistral:7b"
    ollama_client.reset_cache()


def test_resolve_model_uses_preferred_list():
    ollama_client.reset_cache()
    with patch.object(ollama_client, "list_models", return_value=["mistral:7b", "llama3.2:latest"]):
        with patch.dict("os.environ", {"OLLAMA_MODEL": ""}, clear=False):
            assert ollama_client.resolve_model() == "llama3.2:latest"
    ollama_client.reset_cache()


def test_is_available_false_when_no_models():
    ollama_client.reset_cache()
    with patch.object(ollama_client, "list_models", return_value=[]):
        assert ollama_client.is_available() is False
    ollama_client.reset_cache()
