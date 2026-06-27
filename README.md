# DocuMind - Code Documentation & Agentic Codebase Assistant

DocuMind analyzes code structure (Python, JavaScript, Java, SQL) and generates documentation, diagrams, and **grounded answers** about whole projects via a LangGraph agent with multiple retrieval strategies.

## Features

### Analyze & Document (original tool)
- **Code analysis** via AST-style parsers (functions, classes, imports, call graphs, etc.)
- **Input**: paste code, upload files, local folder, uploaded project, or public GitHub repo
- **Languages**: Python, JavaScript, Java, SQL (+ detection for C/C++ extensions)
- **Documentation**: PEP 257 docstrings, README.md, ARCHITECTURE.md (LLM or template fallback)
- **Diagrams**: Mermaid architecture, sequence, dependency, flowchart, structure (+ SVG export)
- **Parse as** dropdown to override language detection

### Ask DocuMind (agentic Q&A)
- **Ask tab** in the web UI: index a folder, then ask questions about the codebase
- **LangGraph ReAct agent** with tool-first retrieval (not vector-RAG-only):
  - **Agentic**: `grep_code`, `read_file`, `find_symbol`, `get_structure`
  - **Vector**: `vector_search` (ChromaDB)
  - **Graph**: `who_calls`, `what_calls`, `impact_of`, `dependencies_of`
  - **Generation**: docstrings, README, diagrams from retrieved code
- Answers cite **file:line** sources; **tool trace** shows which tools the agent used
- Requires project **indexed** (vector store + code graph) before asking

### Project indexing
- **`POST /api/index-project`**: ingest a folder path → vector index + code graph
- Skips `venv`, `node_modules`, `__pycache__`, `.git`, `dist`, `build`, `target`, `.next`, etc.
- Respects root **`.gitignore`** when present
- Canonical **`project_id`** = resolved absolute path (consistent for index + query)
- macOS path fix: `Users/you/project` auto-normalized to `/Users/you/project`

### Evaluation (Phase E)
- Three-way RAGAS comparison: agentic-only vs vector-only vs graph-assisted
- Golden set: `eval/golden_set.jsonl`; reports in `eval/reports/`
- Optional LangSmith tracing for agent runs and tool calls

## Quick start

```bash
git clone <your-repo-url>
cd DocuMind
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # add OPENAI_API_KEY for LLM docs + agent + embeddings
python app.py
```

Open **http://127.0.0.1:5001** (default port **5001** avoids macOS AirPlay on 5000).

### Ask DocuMind workflow

1. Switch to the **Ask DocuMind** tab
2. **Index a project** — folder path, e.g.:
   - `eval/sample_project_data` (Python sample)
   - `eval/sample_java_project_data` (Java sample)
   - `/Users/you/your-django-project` (full absolute path on macOS)
3. Click **Index** — wait for “Ready” (files indexed, venv skipped)
4. Select the project from the dropdown
5. Ask e.g. *Who calls helper in calls.py?* or *What does Calculator.add do?*

### Analyze workflow

1. **Analyze & Diagram** tab → paste or upload code
2. **Analyze Code** → view summary, diagrams, JSON
3. **Generate Documentation** → docstrings / README / ARCHITECTURE (LLM if `OPENAI_API_KEY` is set)

## Environment variables

Copy `.env.example` to `.env`. Key variables:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | LLM docs, agent, embeddings (optional for template-only docs) |
| `LLM_PROVIDER` / `LLM_MODEL` | Chat model (default `gpt-4o-mini`) |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | Vector index (default OpenAI `text-embedding-3-small`) |
| `CHROMA_PERSIST_DIR` | Vector store path (default `.chroma`) |
| `GRAPH_PERSIST_DIR` | Code graph path (default `.graph_store`) |
| `LANGCHAIN_TRACING_V2` / `LANGSMITH_API_KEY` | Optional LangSmith tracing |

Never commit `.env` or API keys.

## Optional: eval harness & tracing

```bash
pip install -r requirements-dev.txt
python eval/run_eval.py              # full 30-question comparison
python eval/run_eval.py --limit 3    # smoke test
```

LangSmith: set `LANGCHAIN_TRACING_V2=true` and `LANGSMITH_API_KEY` in `.env`. Traces tag `project_id`, `endpoint`, and `retrieval_strategy`.

## Running tests

```bash
pytest
pytest --cov=. --cov-report=term-missing
```

## Deployment (Render)

DocuMind runs as a **Python web service** (Gunicorn), not Docker/K8s by default. See `render.yaml`:

```bash
gunicorn --bind 0.0.0.0:$PORT app:app
```

**Note:** Hosted DocuMind cannot index paths on your laptop. For local repos, run DocuMind locally. Render ephemeral disk does not persist indexes across redeploys unless you add persistent storage or an external vector DB.

## Technology stack

- **Backend**: Flask, Gunicorn
- **Agent**: LangGraph + LangChain tools
- **Vector index**: ChromaDB + LlamaIndex chunking
- **Code graph**: NetworkX (parser-driven)
- **LLM**: Provider-agnostic `llm_factory` (OpenAI, Anthropic, …)
- **Frontend**: HTML/CSS/JS, Mermaid.js
- **Eval**: RAGAS, optional LangSmith

## Project structure

```
DocuMind/
├── app.py                    # Flask routes
├── agent.py                  # LangGraph agent
├── project_indexing.py       # Index folder → vector + graph
├── project_ignore.py         # Skip dirs + .gitignore for walks
├── code_parser.py            # Python AST parser
├── javascript_parser.py
├── java_parser.py
├── sql_parser.py
├── vector_index.py / vector_search.py
├── code_graph.py / graph_tools.py / code_tools.py
├── doc_generator.py / diagram_generator.py
├── llm_factory.py / tracing.py / gen_tools.py
├── eval/                     # Golden set + run_eval.py + sample projects
├── templates/ / static/
├── tests/
├── render.yaml
└── requirements.txt
```

## API endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/parse` | POST | Parse single file/snippet |
| `/api/generate-docs` | POST | Docstrings, README, ARCHITECTURE |
| `/api/index-project` | POST | Index folder (`folder_path`) → vector + graph |
| `/api/agent` | POST | Agent Q&A (`project_id`, `message`) |
| `/api/parse-project` | POST | Parse project layout JSON |
| `/api/parse-github-repo` | POST | Clone & parse public repo |
| `/api/generate-project-docs` | POST | Docs for scanned project |
| `/api/generate-svg-flowchart` | POST | SVG flowchart |

### POST /api/index-project

```json
{ "folder_path": "/Users/you/project" }
```

Response includes `project_id`, `ready`, `files_scanned`, skip counts, `chunks_indexed`, graph stats.

### POST /api/agent

```json
{
  "project_id": "/Users/you/project",
  "message": "Who calls helper in calls.py?"
}
```

Response: `answer`, `sources`, `tool_trace`, `tokens`. Returns **409** if the project is not indexed.

## Sample projects

| Path | Language | Use |
|------|----------|-----|
| `eval/sample_project_data/` | Python | Eval golden set + Ask demo |
| `eval/sample_java_project_data/` | Java | Java parser + Ask demo |

## License

Open source for educational and commercial use.
