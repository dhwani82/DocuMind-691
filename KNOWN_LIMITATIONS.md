# Known Limitations (DocuMind Agentic Platform)

Documented constraints for evaluation golden sets and agent prompt design.

## Code knowledge graph (`code_graph.py` / `graph_tools.py`)

### Cross-file qualified calls are resolved via imports

- **What works:** after a two-pass graph build, call targets like `LanguageDetector.detect()` resolve through `from language_detector import LanguageDetector` to the real definition in `language_detector.py`. Same-file chains (`leaf` ← `middle` ← `top`) and `self.method()` inside a class (via `method_calls`) also work.
- **Impact:** `who_calls` / `impact_of` on symbols such as `language_detector.detect` return real transitive callers across project files.

### Instance / variable method calls are not type-resolved

- **What works:** qualified class or module references (`LanguageDetector.detect()`, `os.path.join()`).
- **Limitation:** calls through a local variable are not traced back to the imported type. For example, `d = LanguageDetector(); d.detect()` is stored as callee `d.detect`, not `LanguageDetector.detect`.
- **Limitation:** attribute calls on unknown bindings (`obj.method()`, `s.run()`) remain unresolved stubs such as `s.run`, not `Service.run`.
- **Impact:** `who_calls` / `impact_of` on a method may miss callers that invoke it through a variable or opaque reference, even when the variable was assigned from an imported class.

### `impact_of` traverses call edges only

- **What works:** transitive **caller** chains over `calls` edges (who is affected if this symbol changes).
- **Limitation:** does not include import or inheritance edges in impact propagation.
- **Use instead:** `dependencies_of(file_path)` for a file's import/module graph.

## Vector retrieval (`vector_search.py`)

- Hybrid BM25 fusion helps exact identifier queries but still depends on chunk boundaries from `chunking.py`.
- Local embeddings (`EMBEDDING_PROVIDER=local`) download model weights on first use (not exercised in CI).

## LLM paths

- Live OpenAI chat + embedding calls require `OPENAI_API_KEY` in `.env`; unit tests mock all provider clients.
