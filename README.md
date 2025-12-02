# DocuMind - Code Documentation Tool

DocuMind is a powerful code documentation tool that analyzes Python code structure using AST (Abstract Syntax Tree) parsing. It provides developers with instant insights into their codebase structure.

## Features

- **Code Analysis**: Parse Python code to extract comprehensive structural information
- **Multiple Input Methods**: 
  - Paste code directly into the interface
  - Upload Python files (.py)
- **Detailed Extraction**:
  - Functions (sync, async, nested)
  - Classes with parent classes
  - Methods
  - Global variables
  - Class variables
  - Instance variables
  - Decorators
  - Imports
- **Professional Documentation Generation**:
  - **PEP 257 Compliant Docstrings**: Automatically generate docstrings for functions and classes
  - **README.md**: Generate comprehensive project documentation with setup instructions
  - **ARCHITECTURE.md**: Create detailed architecture documentation with module relationships
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

## Usage

1. Make sure your virtual environment is activated (if using one)

2. Start the Flask server:
```bash
python app.py
```
   Or if using the virtual environment:
```bash
venv\Scripts\python.exe app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. Either:
   - Paste your Python code into the text area, or
   - Upload a Python file using the upload tab

4. Click "Analyze Code" to see the results

5. View the summary or switch to JSON view for detailed output

6. View automatically generated diagrams:
   - **Architecture**: Class structure and relationships
   - **Sequence**: Function call sequences
   - **Dependencies**: Module import relationships

7. Click "Generate Documentation" to create professional documentation:
   - **Docstrings**: Code with PEP 257 compliant docstrings
   - **README.md**: Project documentation
   - **ARCHITECTURE.md**: Architecture and design documentation

### Optional: Enhanced AI Documentation

For AI-powered documentation generation:
1. Get an OpenAI API key from [OpenAI](https://platform.openai.com/)
2. Enter your API key in the optional field before generating documentation
3. The tool will use GPT-4o-mini to generate more sophisticated documentation

**Note**: The tool works without an API key using template-based generation, but AI-generated docs are more comprehensive and context-aware.

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

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Parsing**: Python AST module
- **Diagrams**: Mermaid.js for visualization
- **Documentation**: OpenAI GPT-4o-mini (optional) or template-based
- **API**: RESTful JSON API

## Project Structure

```
DocuMind/
├── app.py              # Flask application and API endpoints
├── code_parser.py      # AST parser implementation
├── doc_generator.py    # Documentation generator with LLM support
├── diagram_generator.py # Mermaid diagram generator
├── templates/
│   └── index.html      # Frontend interface
├── static/
│   ├── style.css       # Styling
│   └── script.js       # Frontend logic
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## API Endpoints

### POST /api/parse

Analyzes Python code and returns structured information.

**Request Body:**
```json
{
  "code": "your python code here"
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

**Request Body:**
```json
{
  "code": "your python code here",
  "api_key": "sk-..." // Optional: OpenAI API key for enhanced generation
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

## License

This project is open source and available for educational and commercial use.

