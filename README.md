# DocuMind - Code Documentation Tool

DocuMind is a powerful code documentation tool that analyzes code structure (Python, JavaScript, SQL, and other languages via pluggable parsers) using AST-style parsing. It provides developers with instant insights into their codebase structure.

## Features

- **Code Analysis**: Parse code to extract comprehensive structural information
- **Multiple Input Methods**: 
  - Paste code directly into the interface
  - Upload source files (Python, JavaScript, SQL, and more)
- **Detailed Extraction**:
  - Functions (sync, async, nested)
  - Classes with parent classes
  - Methods
  - Global variables
  - Class variables
  - Instance variables
  - Decorators
  - Imports
- **Language Detection & Selection**:
  - Automatic language detection based on file extension and code
  - Manual override via a **Parse as** dropdown (Python, JavaScript, C, C++, SQL)
- **Professional Documentation Generation**:
  - **PEP 257 Compliant Docstrings**: Automatically generate docstrings for functions and classes
  - **README.md**: Generate comprehensive project documentation with setup instructions
  - **ARCHITECTURE.md**: Create detailed architecture documentation with:
    - Dependencies and module structure
    - Class overviews (when present)
    - Function counts and key function list
    - **Module Responsibility** section summarizing what the module does
    - **Functional Overview** for each top-level function (purpose + control-flow notes)
  - **LLM-Powered**: Optional OpenAI API integration for AI-enhanced documentation
  - **Template-Based Fallback**: Works without API key using intelligent templates
- **Automatic Diagram Generation**:
  - **Architecture Diagrams**: Class relationships, inheritance, and dependencies
  - **Sequence Diagrams**: Function/method call sequences and interactions
  - **Dependency Diagrams**: Module and import relationships
  - All diagrams use Mermaid.js and reflect actual parsed code relationships
- **Output Formats**:
  - Human-readable summary with statistics
  - Interactive Mermaid diagrams
  - Complete JSON output
  - Generated documentation files (downloadable)
  - Copy-to-clipboard functionality
- **Developer Debug Tools**:
  - `tests/test_parser_debug.py` for quickly inspecting `CodeParser` output
  - `tests/sample_code_for_testing.py` with ready-made code snippets to exercise parsing and documentation

## Installation

1. Clone or download this repository

2. Create a virtual environment (recommended):
```bash
python -m venv venv
```

3. Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On Linux/Mac: `source venv/bin/activate`

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. **OpenAI API key (optional, for AI-powered docs):** set the environment variable **`OPENAI_API_KEY`** so the backend can call OpenAI. The app does **not** read the key from the web UI.
   - **Local:** copy `.env.example` to `.env`, then add `OPENAI_API_KEY=sk-your-key-here`. `.env` is **gitignored**—never commit it. Values load on startup via `python-dotenv`.
   - **Production (e.g. Render):** add **`OPENAI_API_KEY`** in the service **Environment** settings (secret), not in the repository.
   - If **`OPENAI_API_KEY`** is unset, documentation generation still works using the **template-based** path (no LLM).

## Usage

1. Make sure your virtual environment is activated (if using one).

2. Start the Flask development server:
```bash
python app.py
```
   On Windows with a venv, you can use:
```bash
venv\Scripts\python.exe app.py
```
   The app reads **`PORT`** from the environment (default **5001**). On macOS, port **5000** is often taken by AirPlay, so **5001** avoids conflicts.

3. Open your browser at **`http://127.0.0.1:5001`** (or `http://127.0.0.1:$PORT` if you set **`PORT`**).

4. Either:
   - Paste your code into the text area, or
   - Upload a source file using the upload tab (Python/JavaScript/SQL and more)

5. (Optional) Use the **Parse as** dropdown to force a specific language (Python, JavaScript, C, C++, SQL).  
   - If set to **Auto**, DocuMind will detect the language from the filename and/or code.

6. Click **Analyze Code** to see the results.

7. View the summary or switch to JSON view for detailed output.

8. View automatically generated diagrams:
   - **Architecture**: Class structure and relationships
   - **Sequence**: Function call sequences
   - **Dependencies**: Module import relationships

9. Click **Generate Documentation** to create professional documentation:
   - **Docstrings**: Code with PEP 257 compliant docstrings
   - **README.md**: Project documentation
   - **ARCHITECTURE.md**: Architecture and design documentation

### Optional: Enhanced AI Documentation

For AI-powered documentation generation:
1. Get an OpenAI API key from [OpenAI](https://platform.openai.com/).
2. Set **`OPENAI_API_KEY`** in the environment (see **Installation** step 5): `.env` locally, or your host’s env config (e.g. Render **Environment** variables). You can also pass **`api_key`** in **`POST /api/generate-docs`** JSON for programmatic use.
3. With a valid key configured, the backend uses **GPT-4o-mini** for richer docstrings, README, and architecture text.

**Note:** Without **`OPENAI_API_KEY`**, the tool uses **template-based** generation only (no LLM calls).

### Production server (Gunicorn)

For a production-style run (similar to [Render](https://render.com)), install dependencies and start Gunicorn with an explicit port if **`PORT`** is unset locally:

```bash
pip install -r requirements.txt
PORT=5001 gunicorn --bind 0.0.0.0:$PORT app:app
```

On Render, **`PORT`** is set automatically; the blueprint in **`render.yaml`** uses `gunicorn --bind 0.0.0.0:$PORT app:app`.

## Running tests

From the project root with your virtual environment activated:

```bash
pytest
```

With coverage (uses **`.coveragerc`** to omit virtualenvs and cache):

```bash
pytest --cov=. --cov-report=term-missing
```

## Deploying on Render

1. Connect this repository to Render and create a **Web Service** (or use **Blueprints** with **`render.yaml`**).
2. **Build:** `pip install -r requirements.txt` (already in **`render.yaml`**).
3. **Start:** `gunicorn --bind 0.0.0.0:$PORT app:app`.
4. Set **`OPENAI_API_KEY`** in the service **Environment** tab if you want LLM-backed docs (`sync: false` in the YAML means the value is not stored in git—configure it in the dashboard).

## Example Output

The tool provides:
- **Summary Statistics**: Quick overview of code structure counts
- **Detailed Breakdown**: 
  - Function details (name, line number, type, parameters, return types)
  - Class information (name, bases, methods, variables)
  - Import statements
  - Decorators used
  - Variable declarations

## Technology Stack

- **Backend**: Flask (Python), Gunicorn for production
- **Frontend**: HTML, CSS, JavaScript
- **Parsing**: Python AST module
- **Diagrams**: Mermaid.js for visualization
- **Documentation**: OpenAI GPT-4o-mini (optional) or template-based
- **API**: RESTful JSON API

## Project Structure

```
DocuMind/
├── app.py                 # Flask application and API endpoints
├── code_parser.py         # Core Python AST parser
├── javascript_parser.py   # JavaScript parser
├── sql_parser.py          # SQL parser
├── language_detector.py   # Language detection / overrides
├── doc_generator.py       # Documentation (LLM + templates)
├── diagram_generator.py   # Mermaid diagrams
├── svg_generator.py       # SVG flowchart generation
├── project_scanner.py     # Project / repo scanning helpers
├── render.yaml            # Render Blueprint (build + start + env hint)
├── .env.example           # Example environment variables (copy to .env)
├── .coveragerc            # pytest-cov omit patterns
├── templates/
│   └── index.html         # Web UI
├── static/
│   ├── style.css
│   └── script.js
├── tests/
│   ├── conftest.py        # Pytest fixtures (Flask test client)
│   ├── sample_code_for_testing.py
│   ├── test_parser_debug.py
│   └── test_*.py          # Parser, API, diagrams, docs, language, SQL/JS, etc.
├── requirements.txt
└── README.md
```

## API Endpoints

### POST /api/parse

Analyzes code and returns structured information (currently supports Python, JavaScript, and SQL parsing; other languages can still be detected but may not yet have full parser support).

**Request body (JSON):**

| Field        | Required | Description |
|-------------|----------|-------------|
| `code`      | Yes      | Source to parse |
| `filename`  | No       | Hint for detection (extension) |
| `language`  | No       | Override, e.g. `"python"`, `"javascript"`, `"sql"` |

Example:

```json
{
  "code": "your code here",
  "filename": "optional_filename.py",
  "language": "python"
}
```

**Response:**
```json
{
  "summary": {
    "total_functions": 5,
    "sync_functions": 3,
    "async_functions": 1,
    "nested_functions": 1,
    "total_classes": 2,
    "total_methods": 4,
    "global_variables": 3,
    "class_variables": 2,
    "instance_variables": 5,
    "total_decorators": 2,
    "total_imports": 5
  },
  "functions": [...],
  "classes": [...],
  "global_variables": [...],
  "imports": [...],
  "decorators": [...]
}
```

### POST /api/generate-docs

Generates professional documentation for Python code.

**Request body (JSON):**

| Field      | Required | Description |
|-----------|----------|-------------|
| `code`    | Yes      | Python source |
| `api_key` | No       | OpenAI key for this request only (prefer **`OPENAI_API_KEY`** in env) |

Example:

```json
{
  "code": "your python code here",
  "api_key": "sk-..."
}
```

**Response:**
```json
{
  "success": true,
  "used_llm": true,
  "documentation": {
    "docstrings": "code with PEP 257 docstrings...",
    "readme": "# Project Documentation\n\n...",
    "architecture": "# Architecture Documentation\n\n..."
  }
}
```

### Other JSON API routes

All routes accept **`POST`** with JSON unless noted. See **`app.py`** for exact payloads and responses.

| Route | Purpose |
|-------|---------|
| `/api/generate-project-docs` | Documentation for a scanned project payload |
| `/api/parse-project` | Parse a project layout from JSON (paths + file contents) |
| `/api/parse-uploaded-project` | Parse an uploaded project archive |
| `/api/parse-github-repo` | Fetch and parse a public GitHub repository |
| `/api/generate-svg-flowchart` | Generate an SVG flowchart from analyzed code |

## License

This project is open source and available for educational and commercial use.

