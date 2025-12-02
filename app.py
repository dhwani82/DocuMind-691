from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
import ast
import json
from code_parser import CodeParser
from doc_generator import DocumentationGenerator
from diagram_generator import DiagramGenerator
from svg_generator import SVGFlowchartGenerator

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/parse', methods=['POST'])
def parse_code():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        code = data.get('code', '')
        
        if not code:
            return jsonify({'error': 'No code provided'}), 400
        
        parser = CodeParser()
        result = parser.parse(code)
        
        # Generate diagrams
        diagram_gen = DiagramGenerator(result)
        diagrams = {
            'architecture': diagram_gen.generate_architecture_diagram(),
            'sequence': diagram_gen.generate_sequence_diagram(),
            'dependencies': diagram_gen.generate_dependency_diagram(),
            'flowchart': diagram_gen.generate_flowchart(),
            'structure': diagram_gen.generate_structure_diagram()
        }
        result['diagrams'] = diagrams
        
        return jsonify(result)
    except SyntaxError as e:
        return jsonify({'error': f'Syntax error: {str(e)}'}), 400
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
        provider = data.get('provider', 'openai')  # 'openai', 'ollama', or 'template'
        
        # If template mode, don't use LLM
        if provider == 'template':
            provider = 'openai'  # Use openai provider but without API key
            api_key = None
        else:
            api_key = data.get('api_key', None)  # Optional API key
        
        ollama_model = data.get('ollama_model', 'llama2')  # Ollama model name
        ollama_base_url = data.get('ollama_base_url', 'http://localhost:11434')  # Ollama base URL
        
        if not code:
            return jsonify({'error': 'No code provided'}), 400
        
        # Parse the code first
        parser = CodeParser()
        parse_result = parser.parse(code)
        
        # Generate documentation
        doc_generator = DocumentationGenerator(
            api_key=api_key,
            provider=provider,
            ollama_model=ollama_model,
            ollama_base_url=ollama_base_url
        )
        documentation = doc_generator.generate_documentation(code, parse_result)
        
        return jsonify({
            'success': True,
            'documentation': documentation,
            'used_llm': doc_generator.use_llm,
            'provider': provider
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

