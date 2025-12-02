# 🧠 DocuMind - Application Understanding Guide

This document explains how DocuMind works, what each component does, and how to modify or extend the application.

## 📋 Table of Contents

1. [Application Overview](#application-overview)
2. [Architecture Flow](#architecture-flow)
3. [File Structure & Responsibilities](#file-structure--responsibilities)
4. [Core Components Explained](#core-components-explained)
5. [Data Flow](#data-flow)
6. [How to Extend the Application](#how-to-extend-the-application)

---

## 🎯 Application Overview

**DocuMind** is a Python code documentation and structure analyzer that:
- Parses Python code using AST (Abstract Syntax Tree)
- Extracts code structure (functions, classes, variables, imports, etc.)
- Generates professional documentation (docstrings, README, ARCHITECTURE)
- Creates visual diagrams (Architecture, Sequence, Dependencies, Flowchart)
- Provides SVG export for flowcharts

**Technology Stack:**
- **Backend**: Flask (Python web framework)
- **Frontend**: HTML, CSS, JavaScript
- **Code Parsing**: Python's `ast` module
- **Documentation**: OpenAI API (optional) or template-based
- **Diagrams**: Mermaid.js (for web) and custom SVG generator

---

## 🔄 Architecture Flow

```
User Input (Code)
    ↓
Frontend (index.html + script.js)
    ↓
Flask API (app.py)
    ↓
CodeParser (code_parser.py) → AST Parsing
    ↓
Parse Result (JSON)
    ↓
    ├─→ DiagramGenerator (diagram_generator.py) → Mermaid Diagrams
    ├─→ DocumentationGenerator (doc_generator.py) → Docs (LLM/Template)
    └─→ SVGFlowchartGenerator (svg_generator.py) → SVG Flowchart
    ↓
Frontend Display (Results, Diagrams, Documentation)
```

### Step-by-Step Flow:

1. **User submits code** via paste or file upload
2. **Frontend** sends code to `/api/parse` endpoint
3. **CodeParser** parses code using AST and extracts structure
4. **DiagramGenerator** creates Mermaid diagrams from parsed data
5. **Results** displayed in frontend with tabs for different views
6. **User clicks "Generate Documentation"** → `/api/generate-docs`
7. **DocumentationGenerator** creates docs (LLM if API key provided, else templates)
8. **User clicks "Download SVG"** → `/api/generate-svg-flowchart`
9. **SVGFlowchartGenerator** creates SVG from control flow data

---

## 📁 File Structure & Responsibilities

### Backend Files (Python)

#### `app.py` - **Main Flask Application**
**Purpose**: Entry point, API routes, request handling

**Key Responsibilities:**
- Sets up Flask app and CORS
- Defines API endpoints:
  - `GET /` → Serves the main HTML page
  - `POST /api/parse` → Parses code and returns structure + diagrams
  - `POST /api/generate-docs` → Generates documentation
  - `POST /api/generate-svg-flowchart` → Generates SVG flowchart
- Handles errors and returns JSON responses
- Orchestrates calls to other modules

**Key Functions:**
- `index()` - Renders the main page
- `parse_code()` - Handles code parsing request
- `generate_docs()` - Handles documentation generation
- `generate_svg_flowchart()` - Handles SVG generation

---

#### `code_parser.py` - **Code Structure Parser**
**Purpose**: Parses Python code using AST and extracts all structural information

**Key Responsibilities:**
- Uses Python's `ast` module to parse code
- Extracts:
  - Functions (sync, async, nested)
  - Classes (with inheritance)
  - Methods
  - Variables (global, class, instance)
  - Imports
  - Decorators
  - Function/method calls
  - Class instantiations
  - Control flow structures (if/else, for, while, try/except, return, break, continue)

**Key Classes:**
- `CodeParser` - Main parser class
- `CodeVisitor` - AST visitor that traverses the syntax tree

**Key Methods:**
- `parse(code: str)` - Main parsing method, returns dictionary with all extracted data
- `CodeVisitor.visit_*()` - Methods that visit different AST node types

**Output Structure:**
```python
{
    'functions': [...],
    'classes': [...],
    'global_variables': [...],
    'imports': [...],
    'decorators': [...],
    'function_calls': [...],
    'method_calls': [...],
    'class_instantiations': [...],
    'control_flow': [...],
    'summary': {...}
}
```

---

#### `doc_generator.py` - **Documentation Generator**
**Purpose**: Generates professional documentation (docstrings, README, ARCHITECTURE)

**Key Responsibilities:**
- Generates PEP 257 compliant docstrings
- Creates README.md with project overview
- Creates ARCHITECTURE.md with module relationships
- Uses OpenAI API if key provided, else uses templates

**Key Classes:**
- `DocumentationGenerator` - Main generator class

**Key Methods:**
- `generate_documentation(code, parse_result)` - Main entry point
- `_generate_with_llm()` - LLM-based generation
- `_generate_with_templates()` - Template-based fallback
- `_generate_docstrings_llm/template()` - Docstring generation
- `_generate_readme_llm/template()` - README generation
- `_generate_architecture_llm/template()` - ARCHITECTURE generation

**How it works:**
1. Checks if OpenAI API key is available
2. If yes → Uses GPT to generate professional docs
3. If no → Uses template-based generation with parsed data

---

#### `diagram_generator.py` - **Mermaid Diagram Generator**
**Purpose**: Generates Mermaid.js diagrams from parsed code relationships

**Key Responsibilities:**
- Generates 4 types of diagrams:
  1. **Architecture Diagram** - Class relationships and inheritance
  2. **Sequence Diagram** - Function/method call sequences
  3. **Dependencies Diagram** - Import relationships
  4. **Flowchart** - Control flow within functions

**Key Classes:**
- `DiagramGenerator` - Main generator class

**Key Methods:**
- `generate_architecture_diagram()` - Class diagram with relationships
- `generate_sequence_diagram()` - Function call sequences
- `generate_dependency_diagram()` - Import dependencies
- `generate_flowchart()` - Control flow diagrams

**How it works:**
- Uses parsed data (function_calls, method_calls, class_instantiations, imports, control_flow)
- Generates Mermaid syntax
- Returns diagram code that frontend renders using Mermaid.js library

---

#### `svg_generator.py` - **SVG Flowchart Generator**
**Purpose**: Generates SVG images for flowcharts (downloadable)

**Key Responsibilities:**
- Creates SVG flowchart from control flow data
- Handles if/else, for loops, while loops, returns
- Creates proper node connections and loop-back arrows

**Key Classes:**
- `SVGFlowchartGenerator` - Main generator class

**Key Methods:**
- `generate_svg_flowchart(function_name)` - Main entry point
- `_generate_function_svg()` - Generates SVG for a single function
- `_generate_empty_svg()` - Returns empty SVG with message

**How it works:**
1. Selects function with most control flow (or specified function)
2. Processes control flow items (if, for, while, return)
3. Creates nodes (start, decision, process, end)
4. Draws connections with proper labels
5. Returns SVG string

---

### Frontend Files

#### `templates/index.html` - **Main HTML Page**
**Purpose**: User interface structure

**Key Sections:**
- Header with title
- Input section (tabs for paste/upload)
- API key input
- Action buttons (Analyze, Generate Documentation)
- Output section (analysis results)
- Diagrams section (tabs for different diagrams)
- Documentation section (tabs for docstrings, README, ARCHITECTURE)

**Key Elements:**
- Code input textarea
- File upload area
- Tab buttons for switching views
- Diagram containers (Mermaid.js renders here)
- Documentation display areas

---

#### `static/script.js` - **Frontend Logic**
**Purpose**: Handles user interactions, API calls, and UI updates

**Key Functions:**
- `parseCode()` - Sends code to `/api/parse`, displays results
- `generateDocumentation()` - Sends code to `/api/generate-docs`, displays docs
- `downloadSVGFlowchart()` - Gets SVG from `/api/generate-svg-flowchart`, downloads
- `displayResults(data)` - Shows parsed results in summary/JSON view
- `displayDiagrams(diagrams)` - Renders Mermaid diagrams
- `displayDocumentation(docs)` - Shows generated documentation
- `switchTab()`, `switchDiagramTab()`, `switchDocTab()` - Tab switching
- `handleFile()` - File upload handling
- `copyToClipboard()`, `downloadDoc()` - Utility functions

**Key Variables:**
- `currentData` - Stores parsed results
- `currentCode` - Stores original code
- `currentDocumentation` - Stores generated docs

---

#### `static/style.css` - **Styling**
**Purpose**: Visual design and layout

**Key Features:**
- Dark developer-friendly theme
- Blue accent colors (VS Code/GitHub style)
- Responsive design
- Smooth animations and transitions
- Professional card-based layout

**Key Sections:**
- Body/container styles
- Input section styles
- Button styles (primary, secondary)
- Card styles (stat cards, detail sections)
- Tab styles
- Diagram container styles
- Documentation styles

---

### Configuration Files

#### `requirements.txt` - **Python Dependencies**
Lists all required Python packages:
- `flask` - Web framework
- `flask-cors` - CORS support
- `openai` - OpenAI API client (optional)

#### `README.md` - **Project Documentation**
General project information, setup instructions

---

## 🔧 Core Components Explained

### 1. AST Parsing (code_parser.py)

**What is AST?**
- Abstract Syntax Tree - a tree representation of code structure
- Python's `ast` module converts code string into a tree of nodes
- Each node represents a code construct (function, class, if statement, etc.)

**How it works:**
```python
tree = ast.parse(code)  # Convert code to AST
visitor = CodeVisitor()  # Create visitor
visitor.visit(tree)  # Traverse tree and extract info
```

**Visitor Pattern:**
- `CodeVisitor` extends `ast.NodeVisitor`
- Implements `visit_*` methods for each node type
- When visiting a node, extracts relevant information
- Example: `visit_FunctionDef()` extracts function name, parameters, decorators, etc.

---

### 2. Diagram Generation (diagram_generator.py)

**Mermaid.js Syntax:**
- Mermaid is a diagramming library that uses text-based syntax
- Frontend renders Mermaid code into visual diagrams
- Example:
  ```mermaid
  graph TD
      A[Start] --> B[Process]
      B --> C[End]
  ```

**How diagrams are generated:**
1. Uses parsed relationships (function_calls, method_calls, etc.)
2. Builds Mermaid syntax string
3. Returns as string with ```mermaid code blocks
4. Frontend's Mermaid.js library renders it

**Diagram Types:**

**Architecture Diagram:**
- Shows classes and their relationships
- Inheritance (ClassA --> ClassB)
- Method calls (ClassA --> ClassB : calls method)
- Class instantiations (Function --> Class : creates)

**Sequence Diagram:**
- Shows function/method call sequences
- Participants are functions/classes
- Arrows show calls with labels
- Includes loops and return values

**Dependencies Diagram:**
- Shows import relationships
- Modules import other modules
- Color-coded (user code vs external)

**Flowchart:**
- Shows control flow within functions
- Decision nodes (if/else)
- Loop nodes (for/while)
- Process nodes (code blocks)
- Return/End nodes

---

### 3. Documentation Generation (doc_generator.py)

**Two Modes:**

**LLM Mode (with OpenAI API):**
- Sends code and structure to GPT
- Gets professional, contextual documentation
- More natural and comprehensive

**Template Mode (fallback):**
- Uses templates with parsed data
- Fills in function names, parameters, etc.
- More structured but less contextual

**What's Generated:**
1. **Docstrings**: PEP 257 compliant docstrings for all functions/classes
2. **README.md**: Project overview, setup, function list
3. **ARCHITECTURE.md**: Module structure, relationships, design decisions

---

### 4. SVG Generation (svg_generator.py)

**Why SVG?**
- Vector format (scalable)
- Can be downloaded and used in documents
- Better quality than raster images

**How it works:**
1. Gets control flow data for a function
2. Creates nodes (rectangles, diamonds, ovals)
3. Calculates positions
4. Draws connections with arrows
5. Adds labels
6. Returns SVG XML string

**Node Types:**
- **Start/End**: Ovals (blue)
- **Decision**: Diamonds (orange) - for if/while/for
- **Process**: Rectangles (green) - for code blocks
- **Return**: End node (red)

---

## 📊 Data Flow

### Parsing Flow:
```
Code String
  → ast.parse() → AST Tree
  → CodeVisitor.visit() → Extract Info
  → Build Dictionary
  → Return JSON
```

### Diagram Flow:
```
Parse Result
  → DiagramGenerator
  → Extract Relationships
  → Build Mermaid Syntax
  → Return String
  → Frontend Mermaid.js Renders
```

### Documentation Flow:
```
Code + Parse Result
  → DocumentationGenerator
  → Check API Key
  → LLM or Template
  → Generate Docs
  → Return Dictionary
  → Frontend Displays
```

### SVG Flow:
```
Parse Result (control_flow)
  → SVGFlowchartGenerator
  → Select Function
  → Build Nodes & Connections
  → Generate SVG XML
  → Return String
  → Frontend Downloads
```

---

## 🚀 How to Extend the Application

### Adding a New Diagram Type

1. **Add method to `diagram_generator.py`:**
```python
def generate_my_diagram(self) -> str:
    # Your diagram generation logic
    return "```mermaid\n...\n```"
```

2. **Call it in `app.py` in `parse_code()`:**
```python
diagrams = {
    ...
    'my_diagram': diagram_gen.generate_my_diagram()
}
```

3. **Add tab in `templates/index.html`:**
```html
<button class="diagram-tab-btn" onclick="switchDiagramTab('my_diagram')">My Diagram</button>
```

4. **Add container:**
```html
<div id="my_diagram-diagram" class="diagram-content">
    <div class="diagram-container">
        <div class="mermaid" id="my_diagram-mermaid"></div>
    </div>
</div>
```

5. **Update `script.js` `displayDiagrams()`:**
```javascript
renderDiagram('my_diagram-mermaid', diagrams.my_diagram);
```

---

### Adding a New Parser Feature

1. **Add tracking variable in `CodeParser.__init__()`:**
```python
self.my_new_feature = []
```

2. **Add visitor method in `CodeVisitor`:**
```python
def visit_MyNode(self, node):
    # Extract information
    self.parser.my_new_feature.append(...)
    self.generic_visit(node)
```

3. **Include in `parse()` return:**
```python
return {
    ...
    'my_new_feature': self.my_new_feature
}
```

---

### Adding a New API Endpoint

1. **Add route in `app.py`:**
```python
@app.route('/api/my-endpoint', methods=['POST'])
def my_endpoint():
    try:
        data = request.json
        # Your logic
        return jsonify({'result': ...})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

2. **Call from frontend in `script.js`:**
```javascript
async function myFunction() {
    const response = await fetch('/api/my-endpoint', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({...})
    });
    const data = await response.json();
    // Handle response
}
```

---

### Modifying the UI Theme

**Edit `static/style.css`:**
- Change color variables (search for `#3b82f6`, `#1e293b`, etc.)
- Modify gradients in background properties
- Adjust spacing, fonts, shadows

**Key Color Variables:**
- Primary Blue: `#3b82f6`
- Dark Background: `#1e293b`, `#0f172a`
- Light Text: `#e2e8f0`, `#cbd5e1`
- Borders: `#475569`, `#334155`

---

### Adding Support for Another Language

**This would require significant changes:**

1. **Replace AST parser** with language-specific parser
2. **Modify `CodeParser`** to handle new language constructs
3. **Update `CodeVisitor`** with new node types
4. **Adjust diagram generators** for new syntax
5. **Update frontend** validation (file extensions, etc.)

**Current limitation:** Only Python is supported due to AST usage.

---

## 🔍 Key Concepts to Understand

### 1. AST (Abstract Syntax Tree)
- Tree structure representing code
- Each node = code construct
- Visitor pattern traverses tree

### 2. Visitor Pattern
- Design pattern for traversing structures
- `ast.NodeVisitor` visits each node
- Override `visit_*` methods to extract info

### 3. Mermaid.js
- Text-to-diagram library
- Frontend renders Mermaid syntax
- Multiple diagram types supported

### 4. Flask Routes
- `@app.route()` decorator defines endpoints
- GET for pages, POST for API calls
- Returns JSON or HTML

### 5. CORS (Cross-Origin Resource Sharing)
- Allows frontend to call backend API
- `flask-cors` handles this automatically

---

## 🐛 Common Issues & Solutions

### Issue: Diagrams not rendering
**Solution:** Check browser console, ensure Mermaid.js is loaded, check diagram syntax

### Issue: API returns HTML instead of JSON
**Solution:** Check Flask error handling, ensure proper JSON responses

### Issue: SVG download not working
**Solution:** Check `/api/generate-svg-flowchart` endpoint, verify SVG generation

### Issue: Documentation generation fails
**Solution:** Check OpenAI API key (if using LLM), check template generation logic

---

## 📝 Summary

**DocuMind works by:**
1. Parsing Python code into AST
2. Extracting structure using visitor pattern
3. Generating diagrams from relationships
4. Creating documentation from structure
5. Displaying everything in a modern web UI

**Key Files:**
- `app.py` - API and routing
- `code_parser.py` - Code parsing
- `diagram_generator.py` - Diagram creation
- `doc_generator.py` - Documentation generation
- `svg_generator.py` - SVG flowchart creation
- `templates/index.html` - UI structure
- `static/script.js` - Frontend logic
- `static/style.css` - Styling

**To modify:**
- Add features by extending existing classes
- Add endpoints in `app.py`
- Add UI elements in HTML/JS
- Modify styles in CSS

---

**Happy Coding! 🚀**

