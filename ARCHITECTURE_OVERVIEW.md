# DocuMind - Architecture & Design Overview

## 🏗️ System Architecture

DocuMind is a **web-based code documentation and analysis tool** built with a **client-server architecture** using Flask (Python) backend and vanilla JavaScript frontend.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER (Browser)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Frontend (HTML/CSS/JavaScript)                      │   │
│  │  - User Interface (index.html)                      │   │
│  │  - UI Logic (script.js)                             │   │
│  │  - Styling (style.css)                              │   │
│  │  - Mermaid.js (diagram rendering)                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/REST API
┌─────────────────────────────────────────────────────────────┐
│                    SERVER LAYER (Flask)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Endpoints (app.py)                              │   │
│  │  - /api/parse                                        │   │
│  │  - /api/generate-docs                                │   │
│  │  - /api/parse-project                                │   │
│  │  - /api/parse-github-repo                            │   │
│  │  - /api/generate-svg-flowchart                       │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Core Processing Modules                             │   │
│  │  ├─ CodeParser (AST-based parsing)                  │   │
│  │  ├─ LanguageDetector (multi-language support)       │   │
│  │  ├─ DiagramGenerator (Mermaid diagrams)             │   │
│  │  ├─ DocumentationGenerator (LLM/Template-based)     │   │
│  │  ├─ SVGFlowchartGenerator (SVG export)              │   │
│  │  ├─ ProjectScanner (folder/project analysis)       │   │
│  │  └─ Language-specific parsers (JS, SQL)             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│              EXTERNAL SERVICES (Optional)                    │
│  - OpenAI API (for AI-enhanced documentation)               │
│  - GitHub (for repository cloning)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📐 Design Patterns & Principles

### 1. **Separation of Concerns**
- **Frontend**: UI rendering, user interactions, API communication
- **Backend**: Business logic, code parsing, document generation
- **Parsers**: Language-specific parsing logic isolated in separate modules

### 2. **Modular Architecture**
Each component has a single responsibility:
- `CodeParser`: AST parsing and code structure extraction
- `DiagramGenerator`: Visual diagram creation
- `DocumentationGenerator`: Documentation generation
- `ProjectScanner`: Multi-file project analysis

### 3. **Strategy Pattern**
Language detection and parsing use a strategy pattern:
- `LanguageDetector` detects language from filename/code
- `parse_code_auto()` routes to appropriate parser (Python/JavaScript/SQL)

### 4. **Visitor Pattern**
AST parsing uses the Visitor pattern:
- `CodeVisitor` class traverses AST nodes
- Each `visit_*` method handles specific node types

### 5. **Template Method Pattern**
Documentation generation uses templates with optional LLM enhancement:
- Template-based fallback (works without API key)
- LLM enhancement when API key provided

---

## 🔄 Data Flow Architecture

### Single File Analysis Flow

```
User Input (Code/File)
    ↓
Frontend: parseCode()
    ↓
POST /api/parse
    ↓
LanguageDetector.detect()
    ↓
parse_code_auto() → CodeParser/JavaScriptParser/SQLParser
    ↓
AST/Regex Parsing → Extract Structure
    ↓
DiagramGenerator → Generate Mermaid Diagrams
    ↓
Return JSON Response
    ↓
Frontend: displayResults() → Render UI
```

### Project Analysis Flow

```
User Input (Folder/GitHub Repo)
    ↓
Frontend: parseProject() / cloneAndParseRepo()
    ↓
POST /api/parse-project or /api/parse-github-repo
    ↓
ProjectScanner.scan_project()
    ↓
For each file:
    ├─ LanguageDetector.detect()
    ├─ Parse with appropriate parser
    └─ Aggregate results
    ↓
Generate project-level diagrams
    ↓
Return aggregated JSON
    ↓
Frontend: displayProjectSummary() → Render UI
```

### Documentation Generation Flow

```
User clicks "Generate Documentation"
    ↓
POST /api/generate-docs
    ↓
DocumentationGenerator.generate()
    ↓
Check for OpenAI API key
    ├─ If present: Call OpenAI API (GPT-4o-mini)
    └─ If absent: Use template-based generation
    ↓
Generate:
    ├─ Docstrings (PEP 257 compliant)
    ├─ README.md
    └─ ARCHITECTURE.md
    ↓
Return documentation JSON
    ↓
Frontend: displayDocumentation() → Render tabs
```

---

## 🧩 Component Architecture

### Backend Components

#### 1. **app.py** - Flask Application & API Gateway
**Responsibilities:**
- Flask app initialization and CORS configuration
- API endpoint definitions and routing
- Request/response handling
- Error handling and validation
- Orchestration of other modules

**Key Endpoints:**
- `GET /` - Serves main HTML page
- `POST /api/parse` - Single file code parsing
- `POST /api/parse-project` - Project folder parsing
- `POST /api/parse-uploaded-project` - Uploaded project parsing
- `POST /api/parse-github-repo` - GitHub repository parsing
- `POST /api/generate-docs` - Documentation generation
- `POST /api/generate-project-docs` - Project documentation
- `POST /api/generate-svg-flowchart` - SVG flowchart export

**Design Decisions:**
- RESTful API design
- JSON request/response format
- Centralized error handling
- Language-agnostic parsing router

#### 2. **code_parser.py** - Python AST Parser
**Responsibilities:**
- Parse Python code using `ast` module
- Extract code structure (functions, classes, variables, imports)
- Track function/method calls and relationships
- Extract control flow for flowcharts
- Detect code warnings (shadowed variables, etc.)

**Key Classes:**
- `CodeParser` - Main parser class
- `CodeVisitor` - AST visitor for node traversal

**Data Extracted:**
- Functions (sync, async, nested)
- Classes (with inheritance)
- Methods
- Variables (global, local, class, instance)
- Imports and decorators
- Function/method calls
- Control flow structures (if/else, loops, returns)

**Design Decisions:**
- Uses Python's built-in `ast` module (no external dependencies)
- Visitor pattern for clean AST traversal
- Comprehensive data extraction for diagram generation

#### 3. **language_detector.py** - Multi-Language Support
**Responsibilities:**
- Detect programming language from filename extension
- Fallback to code content analysis
- Normalize language names

**Supported Languages:**
- Python (.py)
- JavaScript (.js, .jsx, .ts, .tsx)
- SQL (.sql)

**Design Decisions:**
- Extension-based detection (fast and reliable)
- Content-based fallback for edge cases
- Extensible for new languages

#### 4. **javascript_parser.py** - JavaScript Parser
**Responsibilities:**
- Parse JavaScript/TypeScript code using regex
- Extract functions, classes, variables, imports
- Similar structure to Python parser output

**Design Decisions:**
- Regex-based parsing (lightweight, no tree-sitter dependency)
- Output format matches Python parser for consistency

#### 5. **sql_parser.py** - SQL Parser
**Responsibilities:**
- Parse SQL code
- Extract tables, columns, queries, relationships

**Design Decisions:**
- SQL-specific parsing logic
- Output format consistent with other parsers

#### 6. **diagram_generator.py** - Visual Diagram Generator
**Responsibilities:**
- Generate Mermaid.js diagram syntax
- Create architecture diagrams (class relationships)
- Create sequence diagrams (function call flows)
- Create dependency diagrams (import relationships)
- Create flowchart diagrams (control flow)

**Diagram Types:**
- **Architecture**: Class inheritance and relationships
- **Sequence**: Function/method call sequences
- **Dependencies**: Module import relationships
- **Flowchart**: Control flow within functions

**Design Decisions:**
- Uses Mermaid.js syntax (rendered client-side)
- Diagram generation based on parsed relationships
- Multiple diagram types for different perspectives

#### 7. **doc_generator.py** - Documentation Generator
**Responsibilities:**
- Generate PEP 257 compliant docstrings
- Generate README.md files
- Generate ARCHITECTURE.md files
- Optional OpenAI API integration for enhanced docs

**Generation Modes:**
- **Template-based**: Works without API key, uses intelligent templates
- **LLM-enhanced**: Uses OpenAI GPT-4o-mini when API key provided

**Design Decisions:**
- Dual-mode operation (works with/without API key)
- Template-based fallback ensures functionality
- LLM enhancement for better context awareness

#### 8. **svg_generator.py** - SVG Flowchart Generator
**Responsibilities:**
- Generate SVG images for flowcharts
- Create downloadable flowchart diagrams
- Handle control flow visualization (if/else, loops, returns)

**Node Types:**
- Start/End nodes (ovals)
- Decision nodes (diamonds) - for conditionals
- Process nodes (rectangles) - for code blocks
- Return nodes (end markers)

**Design Decisions:**
- SVG format (vector, scalable, high quality)
- Custom layout algorithm
- Downloadable format for documentation

#### 9. **project_scanner.py** - Project Analysis
**Responsibilities:**
- Scan project directories recursively
- Collect files by extension
- Parse multiple files and aggregate results
- Generate project-level statistics and diagrams

**Features:**
- Recursive directory scanning
- File filtering by extension
- Aggregated parsing results
- Project-level relationship analysis

**Design Decisions:**
- Supports both uploaded folders and GitHub repos
- Aggregates individual file results
- Generates project-wide insights

### Frontend Components

#### 1. **templates/index.html** - User Interface
**Structure:**
- Header and navigation
- Input section (tabs for paste/upload/GitHub)
- Action buttons (Analyze, Generate Documentation)
- Output section (tabs for Summary/JSON/Diagrams/Documentation)
- Project view (for multi-file analysis)

**UI Modes:**
- **Single File Mode**: Analyze individual files
- **Project Mode**: Analyze entire folders/projects

**Design Decisions:**
- Tab-based navigation for different views
- Responsive layout
- Clear separation of input/output areas

#### 2. **static/script.js** - Frontend Logic
**Responsibilities:**
- API communication (fetch requests)
- UI state management
- Tab switching and view management
- Diagram rendering (Mermaid.js integration)
- File upload handling
- Drag-and-drop support
- Error handling and user feedback

**Key Functions:**
- `parseCode()` - Single file parsing
- `parseProject()` - Project parsing
- `generateDocumentation()` - Documentation generation
- `displayResults()` - Render parsed results
- `displayDiagrams()` - Render Mermaid diagrams
- `displayDocumentation()` - Render generated docs

**Design Decisions:**
- Vanilla JavaScript (no framework dependencies)
- Mermaid.js for client-side diagram rendering
- Async/await for API calls
- Comprehensive error handling

#### 3. **static/style.css** - Styling
**Responsibilities:**
- Visual styling and layout
- Responsive design
- Theme and color scheme
- Component styling (buttons, tabs, containers)

---

## 🔌 API Design

### Request/Response Format

All API endpoints use JSON format:

**Request:**
```json
{
  "code": "python code here",
  "filename": "example.py",  // optional
  "api_key": "sk-..."        // optional for docs
}
```

**Response:**
```json
{
  "summary": {...},
  "functions": [...],
  "classes": [...],
  "diagrams": {
    "architecture": "```mermaid\n...\n```",
    "sequence": "```mermaid\n...\n```",
    "dependencies": "```mermaid\n...\n```"
  },
  "language": "python"
}
```

### Error Handling

All endpoints return consistent error format:
```json
{
  "error": "Error message here",
  "detected_language": "python"  // if applicable
}
```

---

## 🎯 Key Design Decisions

### 1. **Multi-Language Support**
- **Decision**: Support Python, JavaScript, and SQL
- **Rationale**: Broader utility for different codebases
- **Implementation**: Language-specific parsers with unified output format

### 2. **AST vs Regex Parsing**
- **Python**: Uses AST (accurate, comprehensive)
- **JavaScript**: Uses regex (lightweight, no dependencies)
- **Rationale**: Balance between accuracy and simplicity

### 3. **Client-Side Diagram Rendering**
- **Decision**: Use Mermaid.js in browser
- **Rationale**: Reduces server load, interactive diagrams
- **Trade-off**: Requires Mermaid.js library in frontend

### 4. **Dual Documentation Mode**
- **Decision**: Template-based + optional LLM enhancement
- **Rationale**: Works without API key, enhanced with AI
- **Benefit**: Accessibility + optional quality boost

### 5. **Project vs Single File**
- **Decision**: Support both modes
- **Rationale**: Different use cases (quick analysis vs full project)
- **Implementation**: Separate endpoints and UI modes

### 6. **SVG Export for Flowcharts**
- **Decision**: Generate SVG for download
- **Rationale**: Vector format, high quality, document-friendly
- **Use case**: Include in documentation, presentations

---

## 🚀 Technology Stack

### Backend
- **Flask**: Web framework
- **Python AST**: Code parsing
- **OpenAI API**: Optional LLM integration
- **Git**: Repository cloning

### Frontend
- **HTML5/CSS3**: Structure and styling
- **Vanilla JavaScript**: No framework dependencies
- **Mermaid.js**: Diagram rendering
- **Fetch API**: HTTP requests

### Development
- **Python 3.x**: Runtime
- **Virtual Environment**: Dependency isolation

---

## 📊 Data Structures

### Parse Result Structure
```python
{
    'summary': {
        'total_functions': int,
        'total_classes': int,
        'global_variables': int,
        ...
    },
    'functions': [
        {
            'name': str,
            'line': int,
            'parameters': [...],
            'return_type': str,
            'is_async': bool,
            'is_nested': bool,
            ...
        }
    ],
    'classes': [
        {
            'name': str,
            'bases': [...],
            'methods': [...],
            'class_variables': [...],
            'instance_variables': [...],
            ...
        }
    ],
    'diagrams': {
        'architecture': str,  # Mermaid syntax
        'sequence': str,
        'dependencies': str,
        'flowchart': str
    },
    'language': str
}
```

---

## 🔒 Security Considerations

1. **API Key Handling**: Client-side input, sent to server (consider server-side storage for production)
2. **File Upload**: Validates file types and sizes
3. **GitHub Cloning**: Validates URLs, uses temporary directories
4. **Error Messages**: Avoids exposing sensitive information

---

## 🧪 Testing

Test files located in `tests/` directory:
- `test_architecture_diagram.py`
- `test_flowchart.py`
- `test_endpoint.py`
- `test_example.py`

---

## 📈 Scalability Considerations

### Current Limitations
- Single-threaded Flask server
- In-memory processing (no caching)
- No database for storing results

### Potential Improvements
- Add caching layer (Redis)
- Database for result storage
- Background job processing for large projects
- WebSocket for real-time progress updates
- Horizontal scaling with load balancer

---

## 🔄 Extension Points

### Adding a New Language
1. Create `{language}_parser.py` with `parse()` method
2. Add language detection in `language_detector.py`
3. Add routing in `parse_code_auto()` function
4. Update frontend to handle new language

### Adding a New Diagram Type
1. Add method to `diagram_generator.py`
2. Call in `app.py` `parse_code()` endpoint
3. Add tab in `index.html`
4. Add rendering in `script.js`

### Adding a New Documentation Format
1. Add method to `doc_generator.py`
2. Add endpoint in `app.py`
3. Add UI tab in `index.html`
4. Add display function in `script.js`

---

## 📝 Summary

DocuMind follows a **modular, extensible architecture** with clear separation between:
- **Frontend** (presentation and interaction)
- **Backend** (processing and generation)
- **Parsers** (language-specific analysis)
- **Generators** (diagrams and documentation)

The design prioritizes:
- **Flexibility**: Multi-language support, multiple input methods
- **Usability**: Works with/without API keys, intuitive UI
- **Extensibility**: Easy to add languages, diagrams, features
- **Maintainability**: Clear module boundaries, single responsibility

This architecture enables the tool to analyze code, generate visualizations, and create comprehensive documentation for both individual files and entire projects.

