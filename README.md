# DocuMind - Code Documentation & Agentic Codebase Assistant

DocuMind analyzes code structure (Python, JavaScript, Java, SQL, and more via a universal fallback parser), generates documentation and diagrams, and answers questions about codebases through a **LangGraph agent** and an optional **floating chat** over analyzed projects.

## Features

### Analyze & Document
- **Deep parsers** for Python, JavaScript, Java, SQL
- **Universal parser** regex fallback for Go, Rust, PHP, Kotlin, and other text-based languages
- **Input**: paste code, upload files, local folder, uploaded project, or public GitHub repo
- **Documentation**: PEP 257 docstrings, README.md, ARCHITECTURE.md (LLM or template fallback)
- **Diagrams**: Mermaid architecture, sequence, dependency, flowchart, structure (+ SVG export)
- **Parse as** dropdown to override language detection

### Ask DocuMind (agentic Q&A — full project)
- **Ask tab**: index a folder, then ask questions with multi-tool retrieval
- **LangGraph ReAct agent** with tool-first retrieval:
  - **Agentic**: `grep_code`, `read_file`, `find_symbol`, `get_structure`
  - **Vector**: `vector_search` (ChromaDB)
  - **Graph**: `who_calls`, `what_calls`, `impact_of`, `dependencies_of`
  - **Generation**: docstrings, README, diagrams from retrieved code
- Answers cite **file:line** sources; **tool trace** shows which tools the agent used
- Requires **indexing** via `POST /api/index-project` first

### Floating chat (quick Q&A on current session)
- **Ask DocuMind AI** launcher (bottom-right) after you analyze or upload a project
- **`POST /api/chat`**: in-memory RAG over the files loaded in the current browser session
- Lighter-weight than the agent tab; no persistent index required

### Project indexing
- **`POST /api/index-project`**: ingest a folder path → vector index + code graph
- Skips `venv`, `node_modules`, `__pycache__`, `.git`, `dist`, `build`, `target`, `.next`, etc.
- Respects root **`.gitignore`** when present
- Canonical **`project_id`** = resolved absolute path (consistent for index + query)
- macOS path fix: `Users/you/project` auto-normalized to `/Users/you/project`

### Evaluation (Phase E)
- Three-way RAGAS comparison: agentic-only vs vector-only vs graph-assisted
- Golden set: `eval/golden_set.jsonl`; reports in `eval/reports/`
- Optional LangSmith tracing

## Quick start

```bash
git clone https://github.com/dhwani82/DocuMind-691.git
cd DocuMind
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # add OPENAI_API_KEY for LLM docs + agent + embeddings
python app.py
```

Open **http://127.0.0.1:5001** (default port **5001** avoids macOS AirPlay on 5000).

### Ask DocuMind workflow (indexed projects)

1. **Ask DocuMind** tab → enter folder path → **Index**
2. Select project from dropdown → ask e.g. *Who calls helper in calls.py?*

### Analyze + floating chat workflow

1. **Analyze & Diagram** → paste/upload/project → **Analyze Code**
2. Open **Ask DocuMind AI** (launcher) → ask about the loaded project

## Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | LLM docs, agent, chat, embeddings |
| `LLM_PROVIDER` / `LLM_MODEL` | Chat model (default `gpt-4o-mini`) |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | Vector index |
| `CHROMA_PERSIST_DIR` / `GRAPH_PERSIST_DIR` | Index persistence |
| `LANGCHAIN_TRACING_V2` / `LANGSMITH_API_KEY` | Optional LangSmith |

Never commit `.env` or API keys.

## Running tests

```bash
pytest
pytest --cov=. --cov-report=term-missing
```

## Deployment (Render)

Python web service via Gunicorn (`render.yaml`). Not Docker/K8s by default. Run locally to index paths on your machine.

## API endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/parse` | POST | Parse single file/snippet |
| `/api/generate-docs` | POST | Docstrings, README, ARCHITECTURE |
| `/api/index-project` | POST | Index folder → vector + graph |
| `/api/agent` | POST | LangGraph agent Q&A |
| `/api/chat` | POST | Session RAG chat over analyzed project |
| `/api/parse-project` | POST | Parse project layout JSON |
| `/api/parse-github-repo` | POST | Clone & parse public repo |

## Sample projects

| Path | Language |
|------|----------|
| `eval/sample_project_data/` | Python |
| `eval/sample_java_project_data/` | Java |

## License

Open source for educational and commercial use.
