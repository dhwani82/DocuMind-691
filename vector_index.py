"""Vector index for project code chunks (comparison RAG arm)."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Optional

import chromadb
from chromadb.api.models.Collection import Collection
from langchain_core.embeddings import Embeddings

from chunking import ChunkConfig, CodeChunk, chunk_file
from llm_factory import get_embedding_model

DEFAULT_CHROMA_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", ".chroma"))


def _collection_name(project_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", project_id).strip("_")
    if not safe:
        raise ValueError("project_id must contain at least one alphanumeric character")
    return f"documind_{safe}"


def _chunk_id(project_id: str, chunk: CodeChunk, index: int) -> str:
    file_path = chunk.metadata.get("file_path", "unknown")
    start_line = chunk.metadata.get("start_line", 0)
    end_line = chunk.metadata.get("end_line", 0)
    return f"{project_id}:{file_path}:{start_line}:{end_line}:{index}"


class VectorStore(ABC):
    """Small interface hiding the concrete vector database implementation."""

    @abstractmethod
    def upsert_chunks(self, project_id: str, chunks: list[CodeChunk]) -> int:
        """Insert or update chunks for a project."""

    @abstractmethod
    def similarity_search(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the most similar chunks for a query string."""

    @abstractmethod
    def is_indexed(self, project_id: str) -> bool:
        """Return True when the project has at least one indexed chunk."""

    @abstractmethod
    def delete_project(self, project_id: str) -> None:
        """Remove all vectors for a project."""


class ChromaVectorStore(VectorStore):
    """ChromaDB-backed vector store persisted to disk."""

    def __init__(
        self,
        persist_dir: str | Path = DEFAULT_CHROMA_DIR,
        embedding_model: Optional[Embeddings] = None,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_model = embedding_model or get_embedding_model()
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))

    def _get_collection(self, project_id: str, create: bool = True) -> Collection:
        name = _collection_name(project_id)
        if create:
            return self._client.get_or_create_collection(name=name)
        return self._client.get_collection(name=name)

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self.embedding_model.embed_documents(texts)

    def _embed_query(self, query: str) -> list[float]:
        return self.embedding_model.embed_query(query)

    def upsert_chunks(self, project_id: str, chunks: list[CodeChunk]) -> int:
        if not chunks:
            return 0

        collection = self._get_collection(project_id, create=True)
        ids = [_chunk_id(project_id, chunk, index) for index, chunk in enumerate(chunks)]
        documents = [chunk.text for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        embeddings = self._embed_texts(documents)

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(chunks)

    def similarity_search(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not self.is_indexed(project_id):
            return []

        collection = self._get_collection(project_id, create=False)
        result = collection.query(
            query_embeddings=[self._embed_query(query)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[dict[str, Any]] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for document, metadata, distance in zip(documents, metadatas, distances):
            hits.append(
                {
                    "text": document,
                    "metadata": metadata or {},
                    "distance": distance,
                }
            )
        return hits

    def is_indexed(self, project_id: str) -> bool:
        name = _collection_name(project_id)
        existing = {collection.name for collection in self._client.list_collections()}
        if name not in existing:
            return False
        return self._get_collection(project_id, create=False).count() > 0

    def delete_project(self, project_id: str) -> None:
        name = _collection_name(project_id)
        try:
            self._client.delete_collection(name=name)
        except Exception:
            return


def ingest_project(
    project_id: str,
    files: list[str],
    *,
    config: Optional[ChunkConfig] = None,
    vector_store: Optional[VectorStore] = None,
    embedding_model: Optional[Embeddings] = None,
    chunker: Callable[[str], list[CodeChunk]] | None = None,
) -> int:
    """Chunk and upsert a list of project files into the vector index."""
    store = vector_store or ChromaVectorStore(embedding_model=embedding_model)
    chunk_fn = chunker or (lambda file_path: chunk_file(file_path, config=config))

    all_chunks: list[CodeChunk] = []
    for file_path in files:
        path = Path(file_path)
        if not path.is_file():
            continue

        relative_path = path.as_posix()
        file_chunks = chunk_fn(str(path))
        for chunk in file_chunks:
            chunk.metadata["file_path"] = relative_path
        all_chunks.extend(file_chunks)

    return store.upsert_chunks(project_id, all_chunks)


def is_indexed(
    project_id: str,
    *,
    vector_store: Optional[VectorStore] = None,
) -> bool:
    """Return whether a project has been ingested into the vector index."""
    store = vector_store or ChromaVectorStore()
    return store.is_indexed(project_id)


def query_project(
    project_id: str,
    query: str,
    *,
    top_k: int = 5,
    vector_store: Optional[VectorStore] = None,
) -> list[dict[str, Any]]:
    """Run a similarity search against an indexed project."""
    store = vector_store or ChromaVectorStore()
    return store.similarity_search(project_id, query, top_k=top_k)
