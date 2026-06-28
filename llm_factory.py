"""Provider-agnostic LLM and embedding factory for DocuMind agents."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Final, Optional

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models.chat_models import BaseChatModel

LLM_PROVIDER_OPENAI: Final = "openai"
LLM_PROVIDER_ANTHROPIC: Final = "anthropic"
LLM_PROVIDER_LLAMA: Final = "llama"
LLM_PROVIDER_GEMINI: Final = "gemini"

EMBEDDING_PROVIDER_OPENAI: Final = "openai"
EMBEDDING_PROVIDER_LOCAL: Final = "local"

SUPPORTED_LLM_PROVIDERS: Final = frozenset(
    {
        LLM_PROVIDER_OPENAI,
        LLM_PROVIDER_ANTHROPIC,
        LLM_PROVIDER_LLAMA,
        LLM_PROVIDER_GEMINI,
    }
)
SUPPORTED_EMBEDDING_PROVIDERS: Final = frozenset(
    {
        EMBEDDING_PROVIDER_OPENAI,
        EMBEDDING_PROVIDER_LOCAL,
    }
)

DEFAULT_LLM_MODELS: Final = {
    LLM_PROVIDER_OPENAI: "gpt-4o-mini",
    LLM_PROVIDER_ANTHROPIC: "claude-3-5-haiku-latest",
}

DEFAULT_EMBEDDING_MODELS: Final = {
    EMBEDDING_PROVIDER_OPENAI: "text-embedding-3-small",
    EMBEDDING_PROVIDER_LOCAL: "BAAI/bge-small-en-v1.5",
}

API_KEY_ENV_VARS: Final = {
    LLM_PROVIDER_OPENAI: "OPENAI_API_KEY",
    LLM_PROVIDER_ANTHROPIC: "ANTHROPIC_API_KEY",
    LLM_PROVIDER_LLAMA: "LLAMA_API_KEY",
    LLM_PROVIDER_GEMINI: "GOOGLE_API_KEY",
}


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _resolve_provider(
    explicit: Optional[str],
    env_var: str,
    default: str,
    supported: frozenset[str],
    label: str,
) -> str:
    provider = _normalize(explicit) or _normalize(os.getenv(env_var)) or default
    if provider not in supported:
        supported_list = ", ".join(sorted(supported))
        raise ValueError(
            f"Unsupported {label} provider '{provider}'. Supported: {supported_list}"
        )
    return provider


def _resolve_model(
    explicit: Optional[str],
    env_var: str,
    provider: str,
    defaults: dict[str, str],
) -> str:
    model = (explicit or os.getenv(env_var) or defaults.get(provider) or "").strip()
    if not model:
        raise ValueError(
            f"No model configured for provider '{provider}'. "
            f"Set {env_var} or pass model= explicitly."
        )
    return model


def _resolve_api_key(provider: str, explicit: Optional[str], *, required: bool) -> Optional[str]:
    env_var = API_KEY_ENV_VARS.get(provider)
    key = (explicit or (os.getenv(env_var) if env_var else None) or "").strip()
    if required and not key:
        raise ValueError(
            f"Missing API key for provider '{provider}'. "
            f"Set {env_var} in the environment or pass api_key= explicitly."
        )
    return key or None


def get_chat_model(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Return a configured LangChain chat model based on environment settings."""
    resolved_provider = _resolve_provider(
        provider,
        "LLM_PROVIDER",
        LLM_PROVIDER_OPENAI,
        SUPPORTED_LLM_PROVIDERS,
        "LLM",
    )

    if resolved_provider in {LLM_PROVIDER_LLAMA, LLM_PROVIDER_GEMINI}:
        raise NotImplementedError(
            f"LLM provider '{resolved_provider}' is reserved for a future extension point. "
            f"Currently supported: {LLM_PROVIDER_OPENAI}, {LLM_PROVIDER_ANTHROPIC}."
        )

    resolved_model = _resolve_model(model, "LLM_MODEL", resolved_provider, DEFAULT_LLM_MODELS)
    resolved_api_key = _resolve_api_key(resolved_provider, api_key, required=True)

    if resolved_provider == LLM_PROVIDER_OPENAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=resolved_model, api_key=resolved_api_key, **kwargs)

    if resolved_provider == LLM_PROVIDER_ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=resolved_model, api_key=resolved_api_key, **kwargs)

    raise ValueError(f"Unsupported LLM provider '{resolved_provider}'")


def _build_local_embedding_model(model_name: str, **kwargs: Any) -> Embeddings:
    """Build a HuggingFace/sentence-transformers embedding model (lazy import)."""
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=model_name, **kwargs)


def get_embedding_model(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Embeddings:
    """Return a configured LangChain embedding model based on environment settings."""
    resolved_provider = _resolve_provider(
        provider,
        "EMBEDDING_PROVIDER",
        EMBEDDING_PROVIDER_OPENAI,
        SUPPORTED_EMBEDDING_PROVIDERS,
        "embedding",
    )
    resolved_model = _resolve_model(
        model,
        "EMBEDDING_MODEL",
        resolved_provider,
        DEFAULT_EMBEDDING_MODELS,
    )

    if resolved_provider == EMBEDDING_PROVIDER_OPENAI:
        from langchain_openai import OpenAIEmbeddings

        resolved_api_key = _resolve_api_key(LLM_PROVIDER_OPENAI, api_key, required=True)
        return OpenAIEmbeddings(model=resolved_model, api_key=resolved_api_key, **kwargs)

    if resolved_provider == EMBEDDING_PROVIDER_LOCAL:
        return _build_local_embedding_model(resolved_model, **kwargs)

    raise ValueError(f"Unsupported embedding provider '{resolved_provider}'")
