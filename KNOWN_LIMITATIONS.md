# Known Limitations (DocuMind Agentic Platform)

Documented constraints for evaluation golden sets and agent prompt design.

## Code knowledge graph (`code_graph.py` / `graph_tools.py`)

### Attribute method calls are not type-resolved

- **What works:** bare function calls (`helper()`), and `self.method()` inside a class (via `method_calls` from `CodeParser`).
- **Limitation:** calls like `obj.method()` or `s.run()` are stored from `function_calls` with callee names such as `s.run`, not resolved to `Service.run`.
- **Impact:** `who_calls` / `impact_of` on `Service.run` may miss callers that invoke the method through a variable reference.

### `impact_of` traverses call edges only

- **What works:** transitive **caller** chains over `calls` edges (who is affected if this symbol changes).
- **Limitation:** does not include import or inheritance edges in impact propagation.
- **Use instead:** `dependencies_of(file_path)` for a file's import/module graph.

## Vector retrieval (`vector_search.py`)

- Hybrid BM25 fusion helps exact identifier queries but still depends on chunk boundaries from `chunking.py`.
- Local embeddings (`EMBEDDING_PROVIDER=local`) download model weights on first use (not exercised in CI).

## LLM paths

- Live OpenAI chat + embedding calls require `OPENAI_API_KEY` in `.env`; unit tests mock all provider clients.
