"""
In-memory RAG for DocuMind chatbot: line-based chunking, optional OpenAI
(text-embedding-3-small) semantic retrieval, with keyword-overlap fallback.
No FAISS; vectors stay in process memory.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import numpy as np

# Words ignored when matching question to chunks (lowercase, word-boundary style).
DEFAULT_STOPWORDS = frozenset(
    {
        "the",
        "is",
        "are",
        "where",
        "what",
        "how",
        "in",
        "of",
        "and",
        "to",
    }
)

EMBEDDING_MODEL = "text-embedding-3-small"
# Safe upper bound for a single embedding request (chars); far below model context limits
_MAX_EMBED_CHARS = 100_000


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r"[A-Za-z0-9_]+", text)


def get_embedding(text: str) -> Optional[np.ndarray]:
    """
    Return an embedding vector for *text* using OpenAI, or None if unavailable or on error.
    """
    if text is None:
        return None
    s = str(text)
    if not s.strip():
        return None
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    s = s[:_MAX_EMBED_CHARS]
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        r = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=s,
        )
        vec = r.data[0].embedding
        return np.array(vec, dtype=np.float32)
    except Exception:
        return None


def _cosine_similarity_matrix(
    question_vec: np.ndarray, chunk_matrix: np.ndarray
) -> np.ndarray:
    """
    For each row in chunk_matrix, compute cosine sim with question_vec.
    similarity = dot(A, B) / (||A|| * ||B||)
    """
    q = question_vec.astype(np.float64)
    m = chunk_matrix.astype(np.float64)
    qn = np.linalg.norm(q)
    if qn < 1e-10:
        return np.zeros(m.shape[0], dtype=np.float64)
    mn = np.linalg.norm(m, axis=1)
    out = (m @ q) / (mn * qn + 1e-10)
    return out


def _copy_chunk_for_output(ch: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "file": ch.get("file", ""),
        "content": ch.get("content", ""),
        "start_line": ch.get("start_line", 0),
        "end_line": ch.get("end_line", 0),
    }


class RAGEngine:
    def __init__(self) -> None:
        self._chunks: List[Dict[str, Any]] = []
        self._embeddings: Optional[np.ndarray] = None
        # shape (n_chunks, dim); set only when build_index embedding step succeeds
        self._stopwords: frozenset = DEFAULT_STOPWORDS

    def chunk_text(
        self,
        content: Optional[str],
        file_path: Optional[str],
        chunk_size: int = 40,
    ) -> List[Dict[str, Any]]:
        """
        Split *content* into chunks of at most *chunk_size* lines.
        Returns a list of dicts with file, content, start_line, end_line (1-based, inclusive).
        """
        if chunk_size < 1:
            chunk_size = 40

        path = (file_path if file_path is not None else "") or ""
        if content is None:
            return []
        if not isinstance(content, str):
            content = str(content)

        lines = content.splitlines()
        if not lines and content.strip() == "":
            return []
        if not lines:
            lines = [""]

        out: List[Dict[str, Any]] = []
        for i in range(0, len(lines), chunk_size):
            block = lines[i : i + chunk_size]
            text = "\n".join(block)
            out.append(
                {
                    "file": path,
                    "content": text,
                    "start_line": i + 1,
                    "end_line": i + len(block),
                }
            )
        return out

    def build_index(self, files: Optional[List[Dict[str, Any]]]) -> None:
        """
        Build in-memory store from a list of { "path", "content" } dicts.
        When OPENAI_API_KEY is set, chunk embeddings (text-embedding-3-small) are computed in batches.
        """
        self._chunks = []
        self._embeddings = None
        if not files:
            return

        for item in files:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if path is None:
                path = ""
            else:
                path = str(path)

            raw = item.get("content")
            if raw is None:
                raw = ""
            elif not isinstance(raw, str):
                raw = str(raw)

            for ch in self.chunk_text(raw, path, chunk_size=40):
                self._chunks.append(ch)

        self._build_chunk_embeddings()

    def _build_chunk_embeddings(self) -> None:
        if not self._chunks:
            return
        api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if not api_key:
            return
        texts = [str(c.get("content") or "")[:_MAX_EMBED_CHARS] for c in self._chunks]
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            batch_size = 100
            rows: List[List[float]] = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                r = client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch,
                )
                for d in sorted(r.data, key=lambda x: x.index):
                    rows.append(d.embedding)
            if len(rows) != len(self._chunks):
                self._embeddings = None
                return
            self._embeddings = np.array(rows, dtype=np.float32)
        except Exception:
            self._embeddings = None

    def retrieve_with_embeddings(
        self, question: Optional[str], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Cosine-similarity search using stored chunk embeddings. Falls back to keyword retrieval
        if the question cannot be embedded or the index is missing embeddings.
        """
        if top_k < 1:
            return []
        if question is None:
            return []
        q = str(question).strip()
        if not q:
            return []
        if not self._chunks:
            return []

        if self._embeddings is None or self._embeddings.size == 0:
            return self._retrieve_keyword(q, top_k)
        n = int(self._embeddings.shape[0])
        if n != len(self._chunks):
            return self._retrieve_keyword(q, top_k)

        qe = get_embedding(q)
        if qe is None or qe.size == 0:
            return self._retrieve_keyword(q, top_k)
        if qe.shape[0] != self._embeddings.shape[1]:
            return self._retrieve_keyword(q, top_k)

        try:
            sims = _cosine_similarity_matrix(qe, self._embeddings)
            if sims.size == 0:
                return self._retrieve_keyword(q, top_k)
            k = min(top_k, n)
            # Higher similarity first; tie: lower index
            best_indices = np.argsort(-sims)[:k]
            out: List[Dict[str, Any]] = []
            for j in best_indices:
                ch = self._chunks[int(j)]
                out.append(_copy_chunk_for_output(ch))
            return out
        except Exception:
            return self._retrieve_keyword(q, top_k)

    def _retrieve_keyword(self, question: str, top_k: int) -> List[Dict[str, Any]]:
        q_words = [
            w.lower()
            for w in _tokenize(question)
            if w.lower() not in self._stopwords and len(w) > 0
        ]
        if not q_words:
            return [dict(_copy_chunk_for_output(c)) for c in self._chunks[: min(top_k, len(self._chunks))]]

        q_set = set(q_words)

        def score_index(idx: int) -> int:
            chunk = self._chunks[idx]
            body = chunk.get("content")
            if body is None:
                return 0
            if not isinstance(body, str):
                body = str(body)
            c_tokens = {w.lower() for w in _tokenize(body) if w.lower() not in self._stopwords}
            return len(q_set & c_tokens)

        best_indices = sorted(
            range(len(self._chunks)),
            key=lambda j: (-score_index(j), j),
        )[:top_k]

        return [_copy_chunk_for_output(self._chunks[j]) for j in best_indices]

    def retrieve(self, question: Optional[str], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        If OPENAI_API_KEY is set and chunk embeddings are available, use semantic retrieval;
        otherwise use keyword-overlap. Embedding failures in semantic mode fall back to keyword search.
        """
        if top_k < 1:
            return []
        if question is None:
            return []
        q = str(question).strip()
        if not q:
            return []
        if not self._chunks:
            return []

        api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if api_key and self._embeddings is not None and self._embeddings.size:
            if self._embeddings.shape[0] == len(self._chunks):
                return self.retrieve_with_embeddings(q, top_k)

        return self._retrieve_keyword(q, top_k)
