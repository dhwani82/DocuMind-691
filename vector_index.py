"""Vector index for project code chunks (comparison RAG arm)."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Final, Optional

from langchain_core.embeddings import Embeddings

from chunking import ChunkConfig, CodeChunk, chunk_file

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection

VECTOR_STORE_PROVIDER_CHROMA: Final = "chroma"
VECTOR_STORE_PROVIDER_PINECONE: Final = "pinecone"

SUPPORTED_VECTOR_STORE_PROVIDERS: Final = frozenset(
    {
        VECTOR_STORE_PROVIDER_CHROMA,
        VECTOR_STORE_PROVIDER_PINECONE,
    }
)

DEFAULT_EMBEDDING_DIMENSION: Final = 1536
DEFAULT_CHROMA_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", ".chroma"))
DEFAULT_PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
DEFAULT_PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")


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


def _resolve_vector_store_provider(explicit: Optional[str] = None) -> str:
    provider = (explicit or os.getenv("VECTOR_STORE_PROVIDER") or VECTOR_STORE_PROVIDER_CHROMA).strip().lower()
    if provider not in SUPPORTED_VECTOR_STORE_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_VECTOR_STORE_PROVIDERS))
        raise ValueError(f"Unsupported vector store provider '{provider}'. Supported: {supported}")
    return provider


def _to_pinecone_filter(where: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not where:
        return None
    return {key: {"$eq": value} for key, value in where.items()}


def _pinecone_metadata(metadata: dict[str, Any], text: str) -> dict[str, Any]:
    """Convert chunk metadata to Pinecone-compatible metadata and store chunk text."""
    payload: dict[str, Any] = {"text": text}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            payload[key] = value
        elif isinstance(value, list):
            payload[key] = [str(item) for item in value]
        else:
            payload[key] = str(value)
    return payload


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
        *,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Return the most similar chunks for a query string."""

    @abstractmethod
    def fetch_chunks(self, project_id: str) -> list[dict[str, Any]]:
        """Return all indexed chunks for a project."""

    @abstractmethod
    def is_indexed(self, project_id: str) -> bool:
        """Return True when the project has at least one indexed chunk."""

    @abstractmethod
    def delete_project(self, project_id: str) -> None:
        """Remove all vectors for a project."""


class ChromaVectorStore(VectorStore):
    """ChromaDB-backed vector store persisted to disk."""

    def __new__(
        cls,
        persist_dir: str | Path = DEFAULT_CHROMA_DIR,
        embedding_model: Optional[Embeddings] = None,
    ) -> ChromaVectorStore:
        if cls is ChromaVectorStore and embedding_model is None:
            resolved_persist = Path(persist_dir).expanduser().resolve()
            default_persist = DEFAULT_CHROMA_DIR.expanduser().resolve()
            if resolved_persist == default_persist and _resolve_vector_store_provider() == VECTOR_STORE_PROVIDER_PINECONE:
                instance = object.__new__(PineconeVectorStore)
                PineconeVectorStore.__init__(instance, embedding_model=embedding_model)
                return instance
        return super().__new__(cls)

    def __init__(
        self,
        persist_dir: str | Path = DEFAULT_CHROMA_DIR,
        embedding_model: Optional[Embeddings] = None,
    ) -> None:
        import chromadb

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        if embedding_model is None:
            from llm_factory import get_embedding_model

            embedding_model = get_embedding_model()
        self.embedding_model = embedding_model
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
        *,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        if not self.is_indexed(project_id):
            return []

        collection = self._get_collection(project_id, create=False)
        result = collection.query(
            query_embeddings=[self._embed_query(query)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
            where=where,
        )

        hits: list[dict[str, Any]] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]

        for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            hits.append(
                {
                    "id": chunk_id,
                    "text": document,
                    "metadata": metadata or {},
                    "distance": distance,
                    "score": 1.0 / (1.0 + float(distance)),
                }
            )
        return hits

    def fetch_chunks(self, project_id: str) -> list[dict[str, Any]]:
        """Return all indexed chunks for a project."""
        if not self.is_indexed(project_id):
            return []

        collection = self._get_collection(project_id, create=False)
        result = collection.get(include=["documents", "metadatas"])

        chunks: list[dict[str, Any]] = []
        for chunk_id, document, metadata in zip(
            result.get("ids", []),
            result.get("documents", []),
            result.get("metadatas", []),
        ):
            chunks.append(
                {
                    "id": chunk_id,
                    "text": document,
                    "metadata": metadata or {},
                }
            )
        return chunks

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


class PineconeVectorStore(VectorStore):
    """Pinecone-backed vector store for cloud deployments."""

    def __init__(
        self,
        *,
        embedding_model: Optional[Embeddings] = None,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
    ) -> None:
        from pinecone import Pinecone, ServerlessSpec

        resolved_api_key = (api_key or os.getenv("PINECONE_API_KEY") or "").strip()
        if not resolved_api_key:
            raise ValueError("Missing PINECONE_API_KEY for Pinecone vector store.")

        resolved_index_name = (index_name or os.getenv("PINECONE_INDEX_NAME") or "").strip()
        if not resolved_index_name:
            raise ValueError("Missing PINECONE_INDEX_NAME for Pinecone vector store.")

        if embedding_model is None:
            from llm_factory import get_embedding_model

            embedding_model = get_embedding_model()

        self.embedding_model = embedding_model
        self.dimension = dimension
        self.index_name = resolved_index_name

        client = Pinecone(api_key=resolved_api_key)
        if not client.has_index(resolved_index_name):
            client.create_index(
                name=resolved_index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud=DEFAULT_PINECONE_CLOUD, region=DEFAULT_PINECONE_REGION),
            )
        self._index = client.Index(resolved_index_name)

    def _namespace(self, project_id: str) -> str:
        return _collection_name(project_id)

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self.embedding_model.embed_documents(texts)

    def _embed_query(self, query: str) -> list[float]:
        return self.embedding_model.embed_query(query)

    def _namespace_vector_count(self, namespace: str) -> int:
        stats = self._index.describe_index_stats()
        namespaces = getattr(stats, "namespaces", None) or {}
        ns_stats = namespaces.get(namespace)
        if ns_stats is None:
            return 0
        return int(getattr(ns_stats, "vector_count", 0) or 0)

    def upsert_chunks(self, project_id: str, chunks: list[CodeChunk]) -> int:
        if not chunks:
            return 0

        namespace = self._namespace(project_id)
        ids = [_chunk_id(project_id, chunk, index) for index, chunk in enumerate(chunks)]
        embeddings = self._embed_texts([chunk.text for chunk in chunks])
        vectors = [
            {
                "id": chunk_id,
                "values": embedding,
                "metadata": _pinecone_metadata(chunk.metadata, chunk.text),
            }
            for chunk_id, chunk, embedding in zip(ids, chunks, embeddings)
        ]
        self._index.upsert(vectors=vectors, namespace=namespace, batch_size=100, show_progress=False)
        return len(chunks)

    def similarity_search(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        *,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        if not self.is_indexed(project_id):
            return []

        namespace = self._namespace(project_id)
        response = self._index.query(
            vector=self._embed_query(query),
            top_k=top_k,
            namespace=namespace,
            filter=_to_pinecone_filter(where),
            include_metadata=True,
        )

        hits: list[dict[str, Any]] = []
        for match in response.matches or []:
            metadata = dict(match.metadata or {})
            text = metadata.pop("text", "")
            hits.append(
                {
                    "id": match.id,
                    "text": text,
                    "metadata": metadata,
                    "score": float(match.score or 0.0),
                }
            )
        return hits

    def fetch_chunks(self, project_id: str) -> list[dict[str, Any]]:
        if not self.is_indexed(project_id):
            return []

        namespace = self._namespace(project_id)
        chunk_ids: list[str] = []
        pagination_token: Optional[str] = None

        while True:
            page = self._index.list_paginated(
                namespace=namespace,
                limit=100,
                pagination_token=pagination_token,
            )
            chunk_ids.extend(vector.id for vector in (page.vectors or []))
            pagination_token = getattr(getattr(page, "pagination", None), "next", None)
            if not pagination_token:
                break

        chunks: list[dict[str, Any]] = []
        for start in range(0, len(chunk_ids), 100):
            batch_ids = chunk_ids[start : start + 100]
            if not batch_ids:
                continue
            fetched = self._index.fetch(ids=batch_ids, namespace=namespace)
            for chunk_id, vector in (fetched.vectors or {}).items():
                metadata = dict(vector.metadata or {})
                text = metadata.pop("text", "")
                chunks.append(
                    {
                        "id": chunk_id,
                        "text": text,
                        "metadata": metadata,
                    }
                )
        return chunks

    def is_indexed(self, project_id: str) -> bool:
        return self._namespace_vector_count(self._namespace(project_id)) > 0

    def delete_project(self, project_id: str) -> None:
        namespace = self._namespace(project_id)
        try:
            self._index.delete(delete_all=True, namespace=namespace)
        except Exception:
            return


def get_vector_store(
    *,
    embedding_model: Optional[Embeddings] = None,
    persist_dir: str | Path | None = None,
    provider: Optional[str] = None,
) -> VectorStore:
    """Return the configured vector store implementation."""
    resolved_provider = _resolve_vector_store_provider(provider)
    if resolved_provider == VECTOR_STORE_PROVIDER_PINECONE:
        return PineconeVectorStore(embedding_model=embedding_model)
    return ChromaVectorStore(
        persist_dir=persist_dir or DEFAULT_CHROMA_DIR,
        embedding_model=embedding_model,
    )


def ingest_project(
    project_id: str,
    files: list[str],
    *,
    config: Optional[ChunkConfig] = None,
    vector_store: Optional[VectorStore] = None,
    embedding_model: Optional[Embeddings] = None,
    chunker: Callable[[str], list[CodeChunk]] | None = None,
    project_root: str | Path | None = None,
) -> int:
    """Chunk and upsert a list of project files into the vector index."""
    store = vector_store or get_vector_store(embedding_model=embedding_model)
    chunk_fn = chunker or (lambda file_path: chunk_file(file_path, config=config))
    root = Path(project_root).resolve() if project_root else None

    all_chunks: list[CodeChunk] = []
    for file_path in files:
        path = Path(file_path).expanduser()
        if not path.is_absolute() and root is not None:
            path = (root / path).resolve()
        else:
            path = path.resolve()
        if not path.is_file():
            continue

        if root is not None:
            try:
                relative_path = path.relative_to(root).as_posix()
            except ValueError:
                relative_path = path.name
        else:
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
    store = vector_store or get_vector_store()
    return store.is_indexed(project_id)


def query_project(
    project_id: str,
    query: str,
    *,
    top_k: int = 5,
    vector_store: Optional[VectorStore] = None,
) -> list[dict[str, Any]]:
    """Run a similarity search against an indexed project."""
    store = vector_store or get_vector_store()
    return store.similarity_search(project_id, query, top_k=top_k)
