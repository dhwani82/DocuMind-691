"""Hybrid vector retrieval exposed as a LangChain tool."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

from langchain_core.tools import BaseTool, StructuredTool
from llama_index.core.schema import TextNode
from llama_index.retrievers.bm25 import BM25Retriever

from vector_index import ChromaVectorStore, VectorStore

DEFAULT_HYBRID_ENABLED = os.getenv("VECTOR_HYBRID_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEFAULT_HYBRID_ALPHA = float(os.getenv("VECTOR_HYBRID_ALPHA", "0.5"))
DEFAULT_RERANK_ENABLED = os.getenv("VECTOR_RERANK_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEFAULT_RERANK_TOP_N = int(os.getenv("VECTOR_RERANK_TOP_N", "20"))
DEFAULT_RERANK_MODE = os.getenv("VECTOR_RERANK_MODE", "lexical").strip().lower()


@dataclass
class SearchFilters:
    """Metadata filters applied before retrieval."""

    language: Optional[str] = None
    path_prefix: Optional[str] = None
    symbol_type: Optional[str] = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _matches_filters(hit: dict[str, Any], filters: Optional[SearchFilters]) -> bool:
    if not filters:
        return True

    metadata = hit.get("metadata", {})
    file_path = str(metadata.get("file_path", ""))

    if filters.language and str(metadata.get("language", "")).lower() != filters.language.lower():
        return False

    if filters.path_prefix and not file_path.startswith(filters.path_prefix):
        return False

    if filters.symbol_type:
        symbol_kind = str(metadata.get("symbol_kind", "")).lower()
        if symbol_kind != filters.symbol_type.lower():
            return False

    return True


def _apply_filters(hits: list[dict[str, Any]], filters: Optional[SearchFilters]) -> list[dict[str, Any]]:
    return [hit for hit in hits if _matches_filters(hit, filters)]


def _normalize_scores(score_map: dict[str, float]) -> dict[str, float]:
    if not score_map:
        return {}

    values = list(score_map.values())
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return {key: 1.0 for key in score_map}

    return {key: (value - minimum) / (maximum - minimum) for key, value in score_map.items()}


def _bm25_score_map(query: str, hits: list[dict[str, Any]]) -> dict[str, float]:
    if not hits:
        return {}

    nodes = [
        TextNode(
            id_=hit["id"],
            text=hit["text"],
            metadata=hit.get("metadata", {}),
        )
        for hit in hits
    ]
    retriever = BM25Retriever(nodes=nodes, similarity_top_k=len(nodes))
    score_map: dict[str, float] = {hit["id"]: 0.0 for hit in hits}

    for node in retriever.retrieve(query):
        score_map[node.node.node_id] = float(node.score or 0.0)

    return score_map


def _fuse_hybrid_scores(
    chunks: list[dict[str, Any]],
    vector_hits: list[dict[str, Any]],
    bm25_scores: dict[str, float],
    *,
    alpha: float,
) -> list[dict[str, Any]]:
    vector_scores = _normalize_scores(
        {hit["id"]: float(hit.get("score", 0.0)) for hit in vector_hits}
    )
    lexical_scores = _normalize_scores(bm25_scores)
    hit_by_id = {chunk["id"]: dict(chunk) for chunk in chunks}
    for hit in vector_hits:
        hit_by_id[hit["id"]] = {**hit_by_id.get(hit["id"], {}), **hit}

    fused: list[dict[str, Any]] = []
    for chunk_id, hit in hit_by_id.items():
        merged = dict(hit)
        merged["score"] = alpha * vector_scores.get(chunk_id, 0.0) + (1.0 - alpha) * lexical_scores.get(
            chunk_id, 0.0
        )
        merged["vector_score"] = vector_scores.get(chunk_id, 0.0)
        merged["bm25_score"] = lexical_scores.get(chunk_id, 0.0)
        fused.append(merged)

    fused.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return fused


def _lexical_rerank(query: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = [term for term in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query) if len(term) > 1]
    if not terms:
        return hits

    def rerank_score(hit: dict[str, Any]) -> float:
        metadata = hit.get("metadata", {})
        text = hit.get("text", "")
        symbol_name = str(metadata.get("symbol_name", ""))
        base = float(hit.get("score", 0.0))
        bonus = 0.0

        for term in terms:
            if term == symbol_name or term in symbol_name.split("."):
                bonus += 3.0
            if f"def {term}" in text or f"class {term}" in text:
                bonus += 2.0
            if term in text:
                bonus += 0.5

        return base + bonus

    reranked = sorted(hits, key=rerank_score, reverse=True)
    for hit in reranked:
        hit["rerank_score"] = rerank_score(hit)
    return reranked


def _maybe_rerank(
    query: str,
    hits: list[dict[str, Any]],
    *,
    enabled: bool,
    mode: str,
    top_k: int,
) -> list[dict[str, Any]]:
    if not enabled or not hits:
        return hits[:top_k]

    if mode == "llm":
        try:
            from llama_index.core.postprocessor import LLMRerank
            from llama_index.core.schema import NodeWithScore, TextNode

            from llm_factory import get_chat_model
            from tracing import RETRIEVAL_VECTOR, apply_tracing_config

            reranker = LLMRerank(
                top_n=top_k,
                llm=apply_tracing_config(
                    get_chat_model(),
                    endpoint="vector_search.rerank",
                    retrieval_strategy=RETRIEVAL_VECTOR,
                ),
            )
            nodes = [
                NodeWithScore(
                    node=TextNode(id_=hit["id"], text=hit["text"], metadata=hit.get("metadata", {})),
                    score=float(hit.get("score", 0.0)),
                )
                for hit in hits
            ]
            reranked_nodes = reranker.postprocess_nodes(nodes, query_str=query)
            return [
                {
                    "id": node.node.node_id,
                    "text": node.node.get_content(),
                    "metadata": node.node.metadata,
                    "score": float(node.score or 0.0),
                }
                for node in reranked_nodes[:top_k]
            ]
        except Exception:
            pass

    return _lexical_rerank(query, hits)[:top_k]


def vector_search(
    project_id: str,
    query: str,
    k: int = 5,
    filters: Optional[SearchFilters] = None,
    *,
    vector_store: Optional[VectorStore] = None,
    hybrid_enabled: Optional[bool] = None,
    hybrid_alpha: Optional[float] = None,
    rerank_enabled: Optional[bool] = None,
    rerank_top_n: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Search indexed project chunks with optional hybrid fusion and reranking."""
    store = vector_store or ChromaVectorStore()
    if not store.is_indexed(project_id):
        return []

    use_hybrid = hybrid_enabled if hybrid_enabled is not None else _env_bool(
        "VECTOR_HYBRID_ENABLED", DEFAULT_HYBRID_ENABLED
    )
    alpha = hybrid_alpha if hybrid_alpha is not None else _env_float(
        "VECTOR_HYBRID_ALPHA", DEFAULT_HYBRID_ALPHA
    )
    use_rerank = rerank_enabled if rerank_enabled is not None else _env_bool(
        "VECTOR_RERANK_ENABLED", DEFAULT_RERANK_ENABLED
    )
    rerank_pool = rerank_top_n if rerank_top_n is not None else _env_int(
        "VECTOR_RERANK_TOP_N", DEFAULT_RERANK_TOP_N
    )
    rerank_mode = os.getenv("VECTOR_RERANK_MODE", DEFAULT_RERANK_MODE)

    candidate_pool = max(k, rerank_pool if use_rerank else k)
    all_chunks = store.fetch_chunks(project_id)
    filtered_chunks = _apply_filters(all_chunks, filters)

    if not filtered_chunks:
        return []

    vector_hits = _apply_filters(
        store.similarity_search(
            project_id,
            query,
            top_k=candidate_pool,
            where={"language": filters.language} if filters and filters.language else None,
        ),
        filters,
    )

    if use_hybrid:
        bm25_scores = _bm25_score_map(query, filtered_chunks)
        ranked = _fuse_hybrid_scores(filtered_chunks, vector_hits, bm25_scores, alpha=alpha)
    else:
        ranked = sorted(vector_hits, key=lambda hit: hit.get("score", 0.0), reverse=True)

    ranked = ranked[:candidate_pool]
    return _maybe_rerank(
        query,
        ranked,
        enabled=use_rerank,
        mode=rerank_mode,
        top_k=k,
    )[:k]


def vector_search_json(
    project_id: str,
    query: str,
    k: int = 5,
    filters: Optional[SearchFilters] = None,
) -> str:
    """JSON wrapper used by the LangChain tool."""
    hits = vector_search(project_id, query, k=k, filters=filters)
    return json.dumps(hits, indent=2)


@dataclass
class VectorSearchTool:
    """LangChain tool wrapper bound to a project id."""

    project_id: str
    vector_store: Optional[VectorStore] = None

    def search(
        self,
        query: str,
        k: int = 5,
        language: Optional[str] = None,
        path_prefix: Optional[str] = None,
        symbol_type: Optional[str] = None,
    ) -> str:
        filters = SearchFilters(
            language=language,
            path_prefix=path_prefix,
            symbol_type=symbol_type,
        )
        hits = vector_search(
            self.project_id,
            query,
            k=k,
            filters=filters,
            vector_store=self.vector_store,
        )
        return json.dumps(hits, indent=2)


def create_vector_search_tool(
    project_id: str,
    *,
    vector_store: Optional[VectorStore] = None,
) -> BaseTool:
    """Create the vector_search LangChain tool for a project."""
    tool = VectorSearchTool(project_id=project_id, vector_store=vector_store)

    return StructuredTool.from_function(
        func=tool.search,
        name="vector_search",
        description=(
            "Semantic and hybrid BM25+vector search over an indexed project codebase. "
            "Returns JSON chunks with file_path, line range, symbol metadata, and scores. "
            "Optional filters: language, path_prefix, symbol_type."
        ),
    )


def create_retrieval_tools(
    project_root: str,
    project_id: str,
    *,
    vector_store: Optional[VectorStore] = None,
    graph_store=None,
) -> list[BaseTool]:
    """Create code-navigation, vector-search, and graph-query tools together."""
    from code_tools import create_code_tools
    from graph_tools import create_graph_tools

    return [
        *create_code_tools(project_root),
        create_vector_search_tool(project_id, vector_store=vector_store),
        *create_graph_tools(project_id, graph_store=graph_store),
    ]


def create_all_tools(
    project_root: str,
    project_id: str,
    *,
    vector_store: Optional[VectorStore] = None,
    graph_store=None,
    api_key: Optional[str] = None,
) -> list[BaseTool]:
    """Create retrieval and generation tools for a project-bound agent."""
    from gen_tools import create_generation_tools

    return [
        *create_retrieval_tools(
            project_root,
            project_id,
            vector_store=vector_store,
            graph_store=graph_store,
        ),
        *create_generation_tools(api_key=api_key),
    ]
