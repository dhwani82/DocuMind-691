# DocuMind — Current Architecture (Baseline)

This document describes the **existing** Flask code-documentation tool as of the Phase 0.2 baseline. It is the reference for what must keep working as the agentic platform is built on top.

## Overview

DocuMind is a Flask web app that accepts source code (paste, file upload, local folder, uploaded project, or GitHub repo), parses it into structured metadata, generates Mermaid/SVG diagrams, and optionally produces documentation (docstrings, README, ARCHITECTURE) via OpenAI or templates.

```
┌─────────────┐     HTTP/JSON      ┌──────────────┐
│  Web UI     │ ─────────────────► │   app.py     │
│ index.html  │                    │ Flask routes │
│ script.js   │ ◄───────────────── │              │
└─────────────┘     JSON/SVG       └──────┬───────┘
                                            │
         ┌──────────────────────────────────┼──────────────────────────┐
         ▼                  ▼              ▼              ▼           ▼
 language_detector   code_parser    javascript_parser  sql_parser  project_scanner
         │                  │              │              │           │
         └──────────────────┴──────────────┴──────────────┴───────────┘
                                            │
                              parse result (dict)
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
           diagram_generator        doc_generator           svg_generator
           (Mermaid diagrams)    (LLM + templates)      (SVG flowcharts)
```

## Core Modules (Protected Assets)

| Module | Role |
|--------|------|
| `code_parser.py` | Python AST parser (`ast` module). Extracts functions, classes, methods, variables, imports, decorators, call graphs, control flow, warnings. |
| `javascript_parser.py` | Regex-based JS/JSX parser. Same-shaped output as Python parser where possible. |
| `sql_parser.py` | SQL parser for tables, columns, foreign-key relationships. |
| `language_detector.py` | Extension-first language detection; fallback regex patterns. Normalized langs: `python`, `javascript`, `cpp`, `c`, `sql`. |
| `project_scanner.py` | Walks a directory tree, skips common junk dirs, parses supported files, aggregates project-level results. |
| `diagram_generator.py` | Builds Mermaid diagrams from parse results: architecture, code architecture, sequence, dependencies, flowchart, structure. SQL gets schema diagrams. |
| `svg_generator.py` | Renders SVG flowcharts from `control_flow` data (Python-focused). |
| `doc_generator.py` | `DocumentationGenerator`: PEP 257 docstrings, README, ARCHITECTURE via OpenAI (`gpt-4o-mini`) or template fallback. |

## Flask Application (`app.py`)

`app.py` is the orchestration layer: routing, request validation, language dispatch, diagram aggregation, and GitHub clone helpers. It should stay thin; new agentic features belong in new modules.

### Helpers in `app.py`

- `parse_code_auto(code, language)` — dispatches to the correct parser; normalizes Python variable fields.
- `normalize_variable_fields(result)` — consistent `name`, `type`, `line`, `source` on variable dicts.
- `generate_per_file_diagrams(file_details)` — per-file architecture/structure/sequence/dependency/flowchart diagrams for project views.
- `clone_github_repo(repo_url)` — shallow `git clone` into a temp directory.

### Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serves `templates/index.html` |
| POST | `/api/parse` | Parse single snippet/file content. Optional `filename`, `language` override. Returns parse result + Mermaid diagrams. |
| POST | `/api/generate-docs` | Parse Python code → generate docstrings, README, ARCHITECTURE. Optional `api_key`; else `OPENAI_API_KEY` env. |
| POST | `/api/generate-project-docs` | Generate docs from aggregated `project_data` JSON. |
| POST | `/api/parse-project` | Parse local folder via `folder_path` → `scan_project()`. |
| POST | `/api/parse-uploaded-project` | Multipart file upload; aggregates multi-file project parse + diagrams. |
| POST | `/api/parse-github-repo` | Clone public GitHub repo → `scan_project()` + diagrams. |
| POST | `/api/generate-svg-flowchart` | Python code → SVG flowchart (`image/svg+xml`). Optional `function_name`. |

### Environment

- `PORT` — server port (default `5001`).
- `OPENAI_API_KEY` — optional; enables LLM doc generation (`python-dotenv` loads `.env` on startup).

## Parse → Diagram Flow

1. **Input** — raw source + optional filename/language.
2. **Detect** — `LanguageDetector.detect()` unless user overrides via `language` field.
3. **Parse** — `parse_code_auto()` → language-specific parser → normalized dict with `summary`, `functions`, `classes`, `imports`, `control_flow`, etc.
4. **Diagram** — `DiagramGenerator(parse_result)` produces Mermaid strings embedded in `diagrams` key:
   - `architecture`, `code_architecture`, `sequence`, `dependencies`, `flowchart`, `structure`
5. **Response** — JSON to frontend; Mermaid rendered client-side.

For **projects**, `scan_project()` or upload/GitHub paths aggregate per-file `file_details`, then generate both `file_diagrams` (per file) and top-level `diagrams` (whole project).

## Parse → Documentation Flow

1. **Parse** — `CodeParser` (single-file endpoints) or pre-aggregated project data.
2. **Generate** — `DocumentationGenerator.generate_documentation()` or `generate_project_documentation()`.
3. **LLM path** — if `OPENAI_API_KEY` / request `api_key` set and `openai` importable → GPT-4o-mini prompts for docstrings, README, ARCHITECTURE.
4. **Template path** — deterministic templates from parse metadata when no key or LLM failure.
5. **Response** — `{ success, documentation: { docstrings, readme, architecture }, used_llm }`.

## Frontend

| Path | Role |
|------|------|
| `templates/index.html` | Single-page UI: paste/upload, language dropdown, analyze, diagrams tabs, doc generation. |
| `static/style.css` | Styling |
| `static/script.js` | API calls, Mermaid rendering, copy/download |

## Tests (`tests/`)

Pytest suite with Flask `test_client` fixture (`conftest.py`). Coverage areas:

- Parsers: `test_parser.py`, `test_javascript_parser.py`, `test_sql_parser.py`, `test_language_detector.py`
- API: `test_api.py`, `test_endpoint.py`
- Diagrams: `test_diagrams.py`, `test_architecture_diagram.py`, `test_flowchart.py`, `test_flowchart_gen.py`
- Docs: `test_docs.py`
- SVG: `test_svg_output.py`
- Integration: `test_flow.py`, `test_example.py`, `test_global_vars.py`
- Debug: `test_parser_debug.py`, `sample_code_for_testing.py`

## Deployment

- **Dev:** `python app.py` (Flask debug, port 5001).
- **Prod:** Gunicorn (`gunicorn --bind 0.0.0.0:$PORT app:app`); `render.yaml` Blueprint for Render.

## Dependency Stack (Baseline)

| Package | Use |
|---------|-----|
| Flask 3.x | Web framework |
| flask-cors | CORS for API |
| gunicorn | Production WSGI |
| openai | Optional LLM docs |
| python-dotenv | `.env` loading |
| requests | HTTP (if used by integrations) |

Test tooling (`pytest`, `pytest-cov`) lives in `requirements-dev.txt`.

## Extension Points for Agentic Platform

New work should **wrap** existing modules as LangGraph tools rather than rewriting them:

- **Parse tool** → `CodeParser` / `JavaScriptParser` / `SQLParser` / `scan_project`
- **Diagram tool** → `DiagramGenerator`, `SVGFlowchartGenerator`
- **Doc tool** → `DocumentationGenerator`
- **Search tools** → grep, read-file, AST traversal, symbol lookup (primary retrieval)
- **Index tools** → vector store (ChromaDB dev) and knowledge graph (NetworkX dev) as additional retrieval

All new LLM calls should route through a future `llm_factory` module; env vars documented in `.env.example`.
