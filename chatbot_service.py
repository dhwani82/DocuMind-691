"""
DocuMind chat: LLM (optional) or template answers from RAG chunks.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

LLM_NOT_IN_CONTEXT = "I could not find this in the uploaded project."


def _format_chunks_for_context(chunks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for i, ch in enumerate(chunks, 1):
        fn = (ch.get("file") or "").strip() or "<unknown>"
        sl = ch.get("start_line", 0)
        el = ch.get("end_line", 0)
        code = ch.get("content", "") or ""
        parts.append(
            f"--- Chunk {i} ---\n"
            f"file: {fn}\n"
            f"start_line: {sl}\n"
            f"end_line: {el}\n"
            f"content:\n{code}\n"
        )
    return "\n".join(parts)


def _template_answer(question: str, chunks: List[Dict[str, Any]]) -> str:
    """When no API key or the LLM call fails: simple explanation from available code."""
    if not chunks:
        return LLM_NOT_IN_CONTEXT

    best = chunks[0]
    content = (best.get("content") or "").strip()
    if len(content) > 500:
        preview = content[:500].rstrip() + "\n…"
    else:
        preview = content

    file_names: List[str] = []
    seen = set()
    for ch in chunks:
        fn = (ch.get("file") or "").strip() or "<unknown>"
        if fn not in seen:
            seen.add(fn)
            file_names.append(fn)
    if len(file_names) <= 5:
        files_summary = ", ".join(file_names) if file_names else "(no paths)"
    else:
        head = ", ".join(file_names[:4])
        files_summary = f"{head}, and {len(file_names) - 4} more file(s)"

    lines: List[str] = [
        "This response uses only the code sections below (no LLM: template / fallback).",
        "",
        f"Relevant files: {files_summary}.",
        "",
        f"Your question: {question[:200] + ('…' if len(question) > 200 else '')}",
        "",
        "Short summary from the best-matching section:",
    ]
    if preview:
        lines.append(preview)
    else:
        lines.append("(This section had no text.)")
    return "\n".join(lines)


def _openai_messages(
    question: str,
    context_text: str,
    chat_history: Optional[List[Dict[str, str]]],
) -> List[Dict[str, str]]:
    system = (
        "You are DocuMind AI, a codebase assistant.\n"
        "Earlier messages in this session are for continuity only: use them to interpret follow-up questions "
        "(e.g. pronouns or 'the function above').\n"
        "Every factual statement must be grounded in the code context in the **last** user message below. "
        "Do not use outside knowledge or invent details not supported by that context.\n"
        f"If the answer is not present in that code context, reply with exactly this sentence and nothing else:\n"
        f"\"{LLM_NOT_IN_CONTEXT}\"\n"
        "Mention relevant filenames naturally when you cite code. Keep answers clear and beginner-friendly.\n"
        "Do not invent files, functions, APIs, or behavior that are not supported by the code context in the last user message."
    )
    user_body = (
        f"## User question (current turn)\n{question}\n\n"
        f"## Code context for this turn (file, line range, and content)\n{context_text}"
    )
    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    if chat_history:
        for m in chat_history:
            if not isinstance(m, dict):
                continue
            role = (m.get("role") or "").strip().lower()
            content = m.get("content")
            if content is None:
                content = ""
            if role in ("user", "assistant") and str(content).strip():
                messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": user_body})
    return messages


def answer_question(
    question: str,
    retrieved_chunks: List[Dict[str, Any]],
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Return a string answer: OpenAI (gpt-4o-mini) when configured, else template fallback.
    *retrieved_chunks* must follow RAG chunk shape (file, content, start_line, end_line).
    """
    q = (question or "").strip()
    if not q:
        return "Question is empty."

    if not retrieved_chunks:
        return LLM_NOT_IN_CONTEXT

    context_text = _format_chunks_for_context(retrieved_chunks)
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()

    if not api_key:
        return _template_answer(q, retrieved_chunks)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        messages = _openai_messages(q, context_text, chat_history)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return _template_answer(q, retrieved_chunks)
        return text
    except Exception:
        return _template_answer(q, retrieved_chunks)
