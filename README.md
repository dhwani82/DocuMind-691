# DocuMind - Code Documentation & Agentic Codebase Assistant

DocuMind analyzes code structure (Python, JavaScript, Java, SQL, and more via a universal fallback parser), generates documentation and diagrams, and answers questions about codebases through a **LangGraph agent** and an optional **floating chat** over analyzed projects.

Persistence, auth, Docker, and optional S3 artifact storage support a fuller product-style workflow on top of the agentic RAG core.

## Features

### Analyze & Document
- **Deep parsers** for Python, JavaScript, Java, SQL
- **Universal parser** regex fallback for Go, Rust, PHP, Kotlin, and other text-based languages
- **Input**: paste code, upload files, local folder, uploaded project, or public GitHub repo
- **Documentation**: PEP 257 docstrings, README.md, ARCHITECTURE.md (LLM or template fallback)
- **Diagrams**: Mermaid architecture, sequence, dependency, flowchart, structure (+ SVG export)
- **S3 artifacts** (optional): generated README, ARCHITECTURE, Mermaid, and SVG uploads with presigned download URLs
- **Parse as** dropdown to override language detection

### Ask DocuMind (agentic Q&A — full project)
- **Ask tab**: index a folder, then ask questions with multi-tool retrieval
- **LangGraph ReAct agent** with tool-first retrieval:
  - **Agentic**: `grep_code`, `read_file`, `find_symbol`, `get_structure`
  - **Vector**: `vector_search` (ChromaDB locally, Pinecone in cloud)
  - **Graph**: `who_calls`, `what_calls`, `impact_of`, `dependencies_of`
  - **Generation**: docstrings, README, diagrams from retrieved code
- Answers cite **file:line** sources; **tool trace** shows which tools the agent used
- Requires **indexing** via `POST /api/index-project` first (JWT required)
- Chat turns persist to **MongoDB** when `MONGODB_URI` is set (resume via `chat_id` / `thread_id`)

### Floating chat (quick Q&A on current session)
- **Ask DocuMind AI** launcher (bottom-right) after you analyze or upload a project
- **`POST /api/chat`**: RAG over files in the current browser session (JWT required)
- Lighter-weight than the agent tab; no persistent vector index required
- With MongoDB: history is stored with `project_id=null` and replayed for follow-ups

### Auth & persistence
- **`POST /api/register`** / **`POST /api/login`**: JWT auth (`flask-jwt-extended`)
- MongoDB collections: `users`, `projects` (index status), `chat_history`
- Indexing tracks `pending` → `indexing` → `ready` / `failed` per authenticated owner

### Project indexing
- **`POST /api/index-project`**: ingest a folder path → vector index + code graph (+ Mongo status)
- Skips `venv`, `node_modules`, `__pycache__`, `.git`, `dist`, `build`, `target`, `.next`, etc.
- Respects root **`.gitignore`** when present
- Canonical **`project_id`** = resolved absolute path (consistent for index + query)
- macOS path fix: `Users/you/project` auto-normalized to `/Users/you/project`

### Vector store (pluggable)
- **`VECTOR_STORE_PROVIDER=chroma`** (default) — local ChromaDB on disk (`.chroma`)
- **`VECTOR_STORE_PROVIDER=pinecone`** — hosted Pinecone for cloud/Render (one index, namespace per project)
- Heavy clients load **lazily**: Chroma and Pinecone are only imported when selected; OpenAI embeddings never load `transformers`/`torch`

### Evaluation (Phase E)
- Three-way RAGAS comparison: agentic-only vs vector-only vs graph-assisted
- Golden set: `eval/golden_set.jsonl`; reports in `eval/reports/`
- Optional LangSmith tracing

## Quick start (local)

```bash
git clone https://github.com/dhwani82/DocuMind-691.git
cd DocuMind
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # add OPENAI_API_KEY, JWT_SECRET_KEY, optional Mongo/S3
python app.py
```

Open **http://127.0.0.1:5001** (default port **5001** avoids macOS AirPlay on 5000).

### Docker Compose

```bash
cp .env.example .env   # set secrets; MONGODB_URI=mongodb://mongo:27017/documind
docker compose up --build
```

- **app** — Flask/Gunicorn on port **5001**
- **mongo** — MongoDB 7 on **27017** (named volume `mongo_data`)

### Ask DocuMind workflow (indexed projects)

1. Register/login → obtain JWT (`Authorization: Bearer <token>`)
2. **Ask DocuMind** tab → enter folder path → **Index**
3. Select project from dropdown → ask e.g. *Who calls helper in calls.py?*

### Analyze + floating chat workflow

1. **Analyze & Diagram** → paste/upload/project → **Analyze Code**
2. Open **Ask DocuMind AI** (launcher) → ask about the loaded project (JWT required for `/api/chat`)

## Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | LLM docs, agent, chat, embeddings |
| `JWT_SECRET_KEY` | JWT signing (set a strong value in production) |
| `MONGODB_URI` | MongoDB connection (users, projects, chat history) |
| `LLM_PROVIDER` / `LLM_MODEL` | Chat model (default `gpt-4o-mini`) |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | Embeddings (`openai` recommended on Render; `local` for offline BGE) |
| `VECTOR_STORE_PROVIDER` | `chroma` (default) or `pinecone` |
| `CHROMA_PERSIST_DIR` | Local Chroma path (default `.chroma`) |
| `PINECONE_API_KEY` / `PINECONE_INDEX_NAME` | Required when `VECTOR_STORE_PROVIDER=pinecone` |
| `GRAPH_PERSIST_DIR` | Code graph path (default `.graph_store`) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `S3_BUCKET_NAME` | Optional S3 artifact uploads |
| `AWS_REGION` | S3 region (default `us-east-1`) |
| `LANGCHAIN_TRACING_V2` / `LANGSMITH_API_KEY` | Optional LangSmith |
| `PORT` | HTTP port (default `5001`) |

Never commit `.env` or API keys. See `.env.example` for the full list.

## Running tests

```bash
pytest
pytest --cov=. --cov-report=term-missing
```

## Deployment

### Docker

```bash
docker build -t documind .
docker run -p 5001:5001 --env-file .env documind
```

Entrypoint matches production: `gunicorn --bind 0.0.0.0:$PORT app:app`.

### Render

Python web service via Gunicorn (`render.yaml`).

**Recommended Render env** (512MB instance):

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
VECTOR_STORE_PROVIDER=pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=documind
OPENAI_API_KEY=...
JWT_SECRET_KEY=...
MONGODB_URI=...   # e.g. MongoDB Atlas
```

- Use **OpenAI embeddings** on Render — local HuggingFace models are too heavy for small instances.
- Use **Pinecone** for persistent vector storage — Render’s ephemeral disk does not keep Chroma indexes across redeploys.
- Run DocuMind **locally** (or mount volumes) to index paths on your laptop; hosted instances cannot read your filesystem.
- The code graph still uses local disk (`.graph_store`) unless you add external graph storage later.

## API endpoints

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/api/register` | POST | — | Create user + JWT |
| `/api/login` | POST | — | Login + JWT |
| `/api/parse` | POST | — | Parse single file/snippet (+ optional S3 Mermaid URLs) |
| `/api/generate-docs` | POST | — | Docstrings, README, ARCHITECTURE (+ optional S3 URLs) |
| `/api/generate-project-docs` | POST | — | Project-level docs (+ optional S3 URLs) |
| `/api/generate-svg-flowchart` | POST | — | SVG flowchart (+ optional S3 URL) |
| `/api/index-project` | POST | JWT | Index folder → vector + graph + Mongo status |
| `/api/agent` | POST | JWT | LangGraph agent Q&A (+ Mongo chat history) |
| `/api/chat` | POST | JWT | Session RAG chat (+ Mongo history when configured) |
| `/api/parse-project` | POST | — | Parse local project folder |
| `/api/parse-github-repo` | POST | — | Clone & parse public repo |

Protected routes expect `Authorization: Bearer <access_token>`.

## Sample projects

| Path | Language |
|------|----------|
| `eval/sample_project_data/` | Python |
| `eval/sample_java_project_data/` | Java |

## License

Open source for educational and commercial use.
