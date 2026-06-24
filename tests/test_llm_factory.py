"""Tests for provider-agnostic LLM and embedding factory."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from llm_factory import (
    EMBEDDING_PROVIDER_LOCAL,
    EMBEDDING_PROVIDER_OPENAI,
    LLM_PROVIDER_ANTHROPIC,
    LLM_PROVIDER_GEMINI,
    LLM_PROVIDER_LLAMA,
    LLM_PROVIDER_OPENAI,
    get_chat_model,
    get_embedding_model,
)


@pytest.fixture(autouse=True)
def clear_llm_env(monkeypatch):
    """Keep factory tests isolated from host .env."""
    for name in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LLAMA_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_get_chat_model_openai_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")

    mock_model = MagicMock(spec=BaseChatModel)
    with patch("langchain_openai.ChatOpenAI", return_value=mock_model) as mock_cls:
        result = get_chat_model()

    mock_cls.assert_called_once_with(model="gpt-4o-mini", api_key="sk-test-openai")
    assert result is mock_model


def test_get_chat_model_anthropic_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-3-5-haiku-latest")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    mock_model = MagicMock(spec=BaseChatModel)
    with patch("langchain_anthropic.ChatAnthropic", return_value=mock_model) as mock_cls:
        result = get_chat_model()

    mock_cls.assert_called_once_with(
        model="claude-3-5-haiku-latest",
        api_key="sk-ant-test",
    )
    assert result is mock_model


def test_get_chat_model_defaults_to_openai_when_env_unset(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")

    with patch("langchain_openai.ChatOpenAI", return_value=MagicMock(spec=BaseChatModel)) as mock_cls:
        get_chat_model()

    mock_cls.assert_called_once_with(model="gpt-4o-mini", api_key="sk-test-openai")


def test_get_chat_model_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")

    with patch("langchain_anthropic.ChatAnthropic", return_value=MagicMock(spec=BaseChatModel)) as mock_cls:
        get_chat_model(
            provider=LLM_PROVIDER_ANTHROPIC,
            model="claude-3-5-sonnet-latest",
            api_key="explicit-key",
        )

    mock_cls.assert_called_once_with(
        model="claude-3-5-sonnet-latest",
        api_key="explicit-key",
    )


@pytest.mark.parametrize("provider", [LLM_PROVIDER_LLAMA, LLM_PROVIDER_GEMINI])
def test_get_chat_model_extension_points_raise(provider):
    with pytest.raises(NotImplementedError, match=provider):
        get_chat_model(provider=provider, model="placeholder", api_key="test-key")


def test_get_chat_model_missing_api_key_raises():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_chat_model(provider=LLM_PROVIDER_OPENAI, model="gpt-4o-mini")


def test_get_embedding_model_openai_from_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")

    mock_embeddings = MagicMock(spec=Embeddings)
    with patch("langchain_openai.OpenAIEmbeddings", return_value=mock_embeddings) as mock_cls:
        result = get_embedding_model()

    mock_cls.assert_called_once_with(
        model="text-embedding-3-small",
        api_key="sk-test-openai",
    )
    assert result is mock_embeddings


def test_get_embedding_model_local_from_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    mock_embeddings = MagicMock(spec=Embeddings)
    with patch(
        "langchain_huggingface.HuggingFaceEmbeddings",
        return_value=mock_embeddings,
    ) as mock_cls:
        result = get_embedding_model()

    mock_cls.assert_called_once_with(model_name="BAAI/bge-small-en-v1.5")
    assert result is mock_embeddings


def test_get_embedding_model_local_default_model(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")

    with patch(
        "langchain_huggingface.HuggingFaceEmbeddings",
        return_value=MagicMock(spec=Embeddings),
    ) as mock_cls:
        get_embedding_model()

    mock_cls.assert_called_once_with(model_name="BAAI/bge-small-en-v1.5")


def test_get_embedding_model_openai_missing_api_key_raises(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_embedding_model()


def test_get_embedding_model_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        get_embedding_model(provider="anthropic", model="voyage-3")
