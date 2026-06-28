"""Tests for vector store provider selection."""

from unittest.mock import MagicMock, patch

import pytest

from vector_index import (
    VECTOR_STORE_PROVIDER_CHROMA,
    VECTOR_STORE_PROVIDER_PINECONE,
    ChromaVectorStore,
    PineconeVectorStore,
    get_vector_store,
)


@pytest.fixture(autouse=True)
def clear_vector_store_env(monkeypatch):
    monkeypatch.delenv("VECTOR_STORE_PROVIDER", raising=False)
    monkeypatch.delenv("PINECONE_API_KEY", raising=False)
    monkeypatch.delenv("PINECONE_INDEX_NAME", raising=False)


def test_get_vector_store_defaults_to_chroma(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", VECTOR_STORE_PROVIDER_CHROMA)

    with patch("vector_index.ChromaVectorStore.__init__", return_value=None) as mock_init:
        store = get_vector_store()

    assert isinstance(store, ChromaVectorStore)
    mock_init.assert_called_once()


def test_get_vector_store_returns_pinecone_when_configured(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", VECTOR_STORE_PROVIDER_PINECONE)
    monkeypatch.setenv("PINECONE_API_KEY", "pc-test")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "documind-test")

    mock_index = MagicMock()
    mock_index.has_index.return_value = True
    mock_client = MagicMock()
    mock_client.has_index.return_value = True
    mock_client.Index.return_value = MagicMock()

    with patch("pinecone.Pinecone", return_value=mock_client) as mock_pinecone_cls:
        store = get_vector_store()

    assert isinstance(store, PineconeVectorStore)
    mock_pinecone_cls.assert_called_once_with(api_key="pc-test")
    mock_client.Index.assert_called_once_with("documind-test")


def test_get_vector_store_creates_pinecone_index_when_missing(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", VECTOR_STORE_PROVIDER_PINECONE)
    monkeypatch.setenv("PINECONE_API_KEY", "pc-test")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "documind-test")

    mock_client = MagicMock()
    mock_client.has_index.return_value = False
    mock_client.Index.return_value = MagicMock()
    mock_serverless = MagicMock()

    with patch("pinecone.Pinecone", return_value=mock_client):
        with patch("pinecone.ServerlessSpec", mock_serverless):
            get_vector_store()

    mock_client.create_index.assert_called_once()
    kwargs = mock_client.create_index.call_args.kwargs
    assert kwargs["name"] == "documind-test"
    assert kwargs["dimension"] == 1536
    assert kwargs["metric"] == "cosine"


def test_chroma_vector_store_bare_call_delegates_to_pinecone(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", VECTOR_STORE_PROVIDER_PINECONE)
    monkeypatch.setenv("PINECONE_API_KEY", "pc-test")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "documind-test")

    mock_client = MagicMock()
    mock_client.has_index.return_value = True
    mock_client.Index.return_value = MagicMock()

    with patch("pinecone.Pinecone", return_value=mock_client):
        store = ChromaVectorStore()

    assert isinstance(store, PineconeVectorStore)


def test_chroma_vector_store_explicit_path_stays_chroma(monkeypatch, tmp_path):
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", VECTOR_STORE_PROVIDER_PINECONE)

    embeddings = MagicMock()
    with patch("chromadb.PersistentClient") as mock_client_cls:
        store = ChromaVectorStore(persist_dir=tmp_path / "chroma", embedding_model=embeddings)

    assert isinstance(store, ChromaVectorStore)
    mock_client_cls.assert_called_once()


def test_get_vector_store_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported vector store provider"):
        get_vector_store(provider="weaviate")
