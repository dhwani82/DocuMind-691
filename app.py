from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
import ast
import json
from code_parser import CodeParser
from doc_generator import DocumentationGenerator
from diagram_generator import DiagramGenerator
from svg_generator import SVGFlowchartGenerator
from language_detector import LanguageDetector
from javascript_parser import JavaScriptParser
from sql_parser import SQLParser

app = Flask(__name__)
CORS(app)

def parse_code_auto(code: str, language: str) -> dict:
    """Parse code automatically based on detected language.
    
    Args:
        code: Source code to parse
        language: Normalized language name (lowercase)
        
    Returns:
        Parsed code result dictionary
    """
    # Ensure language is normalized to lowercase
    lang_normalized = language.lower() if language else 'python'
    
    if lang_normalized == 'python':
        parser = CodeParser()
        result = parser.parse(code)
        # Normalize variable fields: ensure all variables have name, type, line, source
        result = normalize_variable_fields(result)
        return result
    elif lang_normalized == 'javascript':
        parser = JavaScriptParser()
        result = parser.parse(code)
        return result
    elif lang_normalized == 'sql':
        parser = SQLParser()
        result = parser.parse(code)
        return result
    else:
        raise ValueError(f'Language "{lang_normalized}" is not yet supported. Supported languages: python, javascript, sql.')

def normalize_variable_fields(result: dict) -> dict:
    """Normalize variable fields to have consistent structure: name, type, line, source.
    
    Args:
        result: Parse result dictionary
        
    Returns:
        Result with normalized variable fields
    """
    # Normalize global variables
    for var in result.get('global_variables', []):
        var.setdefault('name', var.get('variable', var.get('name', '')))
        var.setdefault('type', var.get('type', 'unknown'))
        var.setdefault('line', var.get('line', 0))
        var.setdefault('source', 'global')
        # Remove old 'variable' key if it exists
        var.pop('variable', None)
    
    # Normalize local variables
    for var in result.get('local_variables', []):
        var.setdefault('name', var.get('variable', var.get('name', '')))
        var.setdefault('type', var.get('type', 'unknown'))
        var.setdefault('line', var.get('line', 0))
        var.setdefault('source', 'local')
        var.pop('variable', None)
    
    # Normalize execution-scope variables
    for var in result.get('execution_scope_variables', []):
        var.setdefault('name', var.get('variable', var.get('name', '')))
        var.setdefault('type', var.get('type', 'unknown'))
        var.setdefault('line', var.get('line', 0))
        var.setdefault('source', 'execution_scope')
        var.pop('variable', None)
    
    # Normalize class variables
    for cls in result.get('classes', []):
        # Class variables
        for var in cls.get('class_variables', []):
            var.setdefault('name', var.get('variable', var.get('name', '')))
            var.setdefault('type', var.get('type', 'unknown'))
            var.setdefault('line', var.get('line', 0))
            var.setdefault('source', 'class_variable')
            var.pop('variable', None)
        
        # Instance variables
        for var in cls.get('instance_variables', []):
            var.setdefault('name', var.get('variable', var.get('name', '')))
            var.setdefault('type', var.get('type', 'unknown'))
            var.setdefault('line', var.get('line', 0))
            var.setdefault('source', 'instance_variable')
            var.pop('variable', None)
    
    return result

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/parse', methods=['POST'])
def parse_code():
    detected_language = None
    lang_normalized = 'python'
    
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        code = data.get('code', '')
        filename = data.get('filename', None)  # Optional filename for language detection
        
        if not code:
            return jsonify({'error': 'No code provided'}), 400
        
        # Detect language with file extension priority
        detected_language = LanguageDetector.detect(filename=filename, code=code)
        
        # Normalize language to lowercase before parsing (force lowercase)
        lang_normalized = (detected_language or 'python').lower()
        
        # Show info message for JavaScript about tree-sitter usage
        info_messages = []
        if lang_normalized == 'javascript':
            info_messages.append({
                'type': 'info',
                'message': 'JavaScript parsing uses regex-based analysis. For more accurate parsing, consider using tree-sitter.'
            })
        
        # Parse code with normalized language (language is already lowercased)
        try:
            result = parse_code_auto(code, lang_normalized)
        except ValueError as e:
            return jsonify({
                'error': str(e),
                'detected_language': lang_normalized,
                'info_messages': info_messages
            }), 400
        except Exception as parse_error:
            # Catch any parsing errors and provide better error message
            import traceback
            error_details = traceback.format_exc()
            print(f"Error parsing {lang_normalized} code: {error_details}")
            return jsonify({
                'error': f'Error parsing {lang_normalized} code: {str(parse_error)}',
                'detected_language': lang_normalized,
                'info_messages': info_messages
            }), 400
        
        # Add language detection info to result
        result['language'] = lang_normalized
        if filename:
            result['filename'] = filename
        if info_messages:
            result['info_messages'] = info_messages
        
        # Generate diagrams
        try:
            diagram_gen = DiagramGenerator(result)
            diagrams = {
                'architecture': diagram_gen.generate_architecture_diagram(),
                'code_architecture': diagram_gen.generate_code_architecture_diagram(),  # New detailed architecture diagram
                'sequence': diagram_gen.generate_sequence_diagram(),
                'dependencies': diagram_gen.generate_dependency_diagram(),
                'flowchart': diagram_gen.generate_flowchart(),
                'structure': diagram_gen.generate_structure_diagram()
            }
            result['diagrams'] = diagrams
        except Exception as diagram_error:
            # If diagram generation fails, still return the parse result
            import traceback
            error_details = traceback.format_exc()
            print(f"Error generating diagrams: {error_details}")
            result['diagrams'] = {}
            result['diagram_error'] = f'Error generating diagrams: {str(diagram_error)}'
        
        return jsonify(result)
    except SyntaxError as e:
        # Only catch SyntaxError for Python code
        if lang_normalized == 'python':
            return jsonify({'error': f'Syntax error: {str(e)}'}), 400
        else:
            # For non-Python languages, SyntaxError shouldn't occur
            import traceback
            error_details = traceback.format_exc()
            print(f"Unexpected SyntaxError for {lang_normalized}: {error_details}")
            return jsonify({'error': f'Error parsing {lang_normalized} code: {str(e)}'}), 500
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error parsing code: {error_details}")
        return jsonify({'error': f'Error parsing code: {str(e)}'}), 500

@app.route('/api/generate-docs', methods=['POST'])
def generate_documentation():
    """Generate professional documentation for the provided code."""
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        code = data.get('code', '')
        
        if not code:
            return jsonify({'error': 'No code provided'}), 400
        
        # Parse the code first
        parser = CodeParser()
        parse_result = parser.parse(code)
        
        # Generate documentation (API key is read from environment variable)
        doc_generator = DocumentationGenerator()
        documentation = doc_generator.generate_documentation(code, parse_result)
        
        return jsonify({
            'success': True,
            'documentation': documentation,
            'used_llm': doc_generator.use_llm
        })
    except SyntaxError as e:
        return jsonify({'error': f'Syntax error: {str(e)}'}), 400
    except ImportError as e:
        return jsonify({'error': f'Import error: {str(e)}. Please ensure all dependencies are installed.'}), 500
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error generating documentation: {error_details}")
        return jsonify({'error': f'Error generating documentation: {str(e)}'}), 500

@app.route('/api/generate-svg-flowchart', methods=['POST'])
def generate_svg_flowchart():
    """Generate SVG flowchart for the provided code."""
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        code = data.get('code', '')
        function_name = data.get('function_name', None)
        
        if not code:
            return jsonify({'error': 'No code provided'}), 400
        
        # Parse the code
        parser = CodeParser()
        parse_result = parser.parse(code)
        
        # Generate SVG flowchart
        svg_generator = SVGFlowchartGenerator(parse_result)
        svg_content = svg_generator.generate_svg_flowchart(function_name=function_name)
        
        return Response(
            svg_content,
            mimetype='image/svg+xml',
            headers={'Content-Disposition': 'attachment; filename=flowchart.svg'}
        )
    except SyntaxError as e:
        return jsonify({'error': f'Syntax error: {str(e)}'}), 400
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error generating SVG flowchart: {error_details}")
        return jsonify({'error': f'Error generating SVG flowchart: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001)

