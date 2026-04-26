# DocuMind

DocuMind is a code documentation and analysis tool. It parses source with **deep structural** parsers for **Python**, **JavaScript**, and **SQL**, uses a **universal regex fallback** for other text-based languages, summarizes structure, renders **Mermaid** diagrams, and can generate **docstrings**, **README**, and **architecture** text using **templates** or an optional **OpenAI** model.

## Features

- **Code analysis**: Extract functions (sync, async, nested), classes (bases, methods), variables, decorators, imports, control flow, and more (varies by language).
- **Inputs**:
  - Paste code in the web UI
  - Upload a single file
  - Upload a **project** (multiple files)
  - **Local folder**: `POST /api/parse-project` with a server-accessible path
  - **GitHub**: clone and parse via `POST /api/parse-github-repo`
- **Language handling**:
  - **Parse as** override or **Auto** detection from filename and content
  - **Deep structural parsing** (AST-level or project-specific where implemented): **Python**, **JavaScript/JSX** (including **TypeScript/TSX** on the same parser path), and **SQL**
  - **Universal fallback parsing** (regex/text heuristics) for all other text-based code and markup, including: **Java**, **C**, **C++**, **C#**, **Go**, **Rust**, **Ruby**, **PHP**, **Swift**, **Kotlin**, **HTML**, **CSS**, **JSON**, **YAML**, **XML**, and similar files, so projects are still ingested, summarized, and available to the **chatbot/RAG** without being marked unsupported
- **Documentation generation**:
  - **PEP 257-style docstrings** (Python-oriented pipeline)
  - **README.md** and **ARCHITECTURE.md**-style outputs with module responsibility and functional overview where data is available
  - **LLM** (optional `OPENAI_API_KEY`) or **template-only** fallback
- **Diagrams** (Mermaid), including:
  - Architecture, **code architecture**, sequence, dependencies, structure, flowchart
  - **Project** responses add **`file_diagrams`** (per-file diagrams, including per-function flowcharts where applicable)
- **SVG flowcharts**: `POST /api/generate-svg-flowchart` returns downloadable SVG (Python parse path).
- **Developer helpers**:
  - `tests/test_parser_debug.py` — quick `CodeParser` inspection
  - `tests/sample_code_for_testing.py` — sample snippets for manual tests

## Requirements

- Python 3.x
- Dependencies in `requirements.txt` (Flask, flask-cors, openai, python-dotenv, pytest, etc.)

## Installation

1. Clone or download this repository.

2. Create a virtual environment (recommended):

```bash
python -m venv venv
```

3. Activate it:

   - **Windows:** `venv\Scripts\activate`
   - **Linux/macOS:** `source venv/bin/activate`

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. **OpenAI (optional):** for LLM-backed documentation, set **`OPENAI_API_KEY`**. The web UI does not read the key; the server uses the environment (or an optional `api_key` field on some JSON APIs).

   - **Local:** copy `.env.example` to `.env` and set `OPENAI_API_KEY=sk-...`. `.env` is gitignored.
   - **Production (e.g. Render):** set **`OPENAI_API_KEY`** in the host’s environment/secrets, not in the repo.

If **`OPENAI_API_KEY`** is unset, documentation still runs on **templates** only.

## Usage (local web app)

1. Activate your virtual environment if you use one.

2. Start the Flask dev server:

```bash
python app.py
```

Or explicitly:

```bash
venv\Scripts\python.exe app.py
```

3. Open **http://127.0.0.1:5001** (default). Port **5001** avoids macOS AirPlay on **5000**. Override with the **`PORT`** environment variable.

4. Paste code, upload a file, or use project / GitHub flows in the UI as provided.

5. Use **Analyze** / **Generate documentation** actions as needed; switch between summary, JSON, and diagram tabs when available.

**Note:** `app.py` binds **`127.0.0.1`** in debug mode (local only). For a public deployment, use a production WSGI server (see **Deployment**).

### Optional: LLM documentation

1. Obtain an API key from [OpenAI](https://platform.openai.com/).
2. Configure **`OPENAI_API_KEY`** (see step 5 under **Installation**).
3. With a key set, the backend can use **GPT-4o-mini** for richer text; without it, outputs are template-based.

## Testing

Run the test suite with:

```bash
pytest
```

With coverage (if configured):

```bash
pytest --cov=. --cov-report=term-missing
```

## Deployment (Render)

This repo includes **`render.yaml`** (Blueprint-style) using **gunicorn**:

```bash
gunicorn --bind 0.0.0.0:$PORT app:app
```

Set secrets such as **`OPENAI_API_KEY`** in the Render dashboard; do not commit them to `render.yaml`.

## Project structure

```
DocuMind/
├── app.py                 # Flask app and HTTP API
├── code_parser.py         # Python parser
├── javascript_parser.py   # JavaScript parser
├── sql_parser.py          # SQL parser
├── language_detector.py   # Language detection / normalization
├── universal_parser.py   # Regex fallback for non–Python/JS/SQL text sources
├── project_scanner.py     # Folder scan + aggregate parse
├── doc_generator.py       # Doc generation (LLM + templates)
├── diagram_generator.py   # Mermaid diagram generation
├── svg_generator.py       # SVG flowchart generation
├── templates/
│   └── index.html         # Web UI
├── static/
│   ├── style.css
│   └── script.js
├── tests/                 # pytest tests
├── requirements.txt
├── render.yaml            # Render deploy blueprint
├── .env.example           # Example environment file
└── README.md
```

## API reference

All JSON endpoints expect **`Content-Type: application/json`** unless noted.

### `POST /api/parse`

Parse a single code string.

**Body:**

```json
{
  "code": "your code",
  "filename": "optional.py",
  "language": "python"
}
```

`language` may be omitted or `"auto"`. Supported overrides align with parsers: **`python`**, **`javascript`**, **`sql`** (see **Language handling** above).

**Response:** Parse result plus **`diagrams`** (e.g. `architecture`, `code_architecture`, `sequence`, `dependencies`, `flowchart`, `structure`), and optional **`info_messages`** / **`language`**.

### `POST /api/generate-docs`

Generate docstrings / README / architecture text from **Python** source (uses `CodeParser`).

**Body:**

```json
{
  "code": "def foo(): pass",
  "api_key": "sk-..."
}
```

`api_key` is optional if `OPENAI_API_KEY` is set.

**Response:** `success`, `used_llm`, `documentation` (`docstrings`, `readme`, `architecture`, …).

### `POST /api/generate-project-docs`

Generate documentation from an aggregated **project** parse result.

**Body:**

```json
{
  "project_data": { },
  "api_key": "sk-..."
}
```

### `POST /api/parse-project`

Parse a project directory on the **machine running the server**.

**Body:**

```json
{
  "folder_path": "/absolute/path/to/project"
}
```

**Response:** Aggregated parse data, **`diagrams`** (whole project), and **`file_diagrams`** (per file).

### `POST /api/parse-uploaded-project`

**`multipart/form-data`** with field **`files`** (multiple files). Supported extensions include `.py`, `.js`, `.jsx`, `.sql`, and others listed in `app.py` (see source for the current set).

**Response:** Same aggregate shape as project parse, including **`diagrams`** and **`file_diagrams`**.

### `POST /api/parse-github-repo`

Clone a GitHub repo to a temporary directory and parse it.

**Body:**

```json
{
  "repo_url": "https://github.com/org/repo.git"
}
```

**Response:** Aggregate parse plus **`github_repo_url`**, **`cloned_path`**, **`detected_languages`**, **`diagrams`**, **`file_diagrams`**.

**Requirements:** `git` available on the server; network access to GitHub.

### `POST /api/generate-svg-flowchart`

**Body:**

```json
{
  "code": "def foo():\n    return 1\n",
  "function_name": "foo"
}
```

**Response:** `image/svg+xml` attachment **`flowchart.svg`** (Python-only parse path).

## Technology stack

- **Backend:** Flask (Python), flask-cors, gunicorn (production)
- **Frontend:** HTML, CSS, JavaScript
- **Parsing:** `ast` (Python), custom JS/SQL parsers
- **Diagrams:** Mermaid (strings for rendering in the UI)
- **Docs:** OpenAI API (optional) or templates

## License

This project is open source and available for educational and commercial use.
