from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
import ast
import json
import os
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any
from code_parser import CodeParser
from doc_generator import DocumentationGenerator
from diagram_generator import DiagramGenerator
from svg_generator import SVGFlowchartGenerator
from language_detector import LanguageDetector
from javascript_parser import JavaScriptParser
from sql_parser import SQLParser
from project_scanner import scan_project

app = Flask(__name__)
CORS(app)

def generate_per_file_diagrams(file_details: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Generate diagrams for each file individually.
    
    For each file:
    - Generate a Structure Diagram only for that single file
    - Generate a Flowchart per top-level function or class method in that file
    - Generate a Sequence Diagram only for that file's function interactions
    
    Args:
        file_details: List of file detail dictionaries from parse result
        
    Returns:
        Dictionary mapping file paths to their diagrams
    """
    file_diagrams = {}
    
    for file_detail in file_details:
        file_path = file_detail.get('path', 'unknown')
        
        # Skip files with errors
        if file_detail.get('error'):
            file_diagrams[file_path] = {
                'architecture': None,
                'structure': None,
                'sequence': None,
                'dependencies': None,
                'flowchart': None,
                'flowcharts': {},
                'error': file_detail.get('error')
            }
            continue
        
        try:
            # Create a parse result structure for this single file
            single_file_result = {
                'functions': file_detail.get('functions', []),
                'classes': file_detail.get('classes', []),
                'function_calls': file_detail.get('function_calls', []),
                'method_calls': file_detail.get('method_calls', []),
                'class_instantiations': file_detail.get('class_instantiations', []),
                'imports': file_detail.get('imports', []),
                'control_flow': file_detail.get('control_flow', []),
                'import_usage': file_detail.get('import_usage', []),
                'global_variables': file_detail.get('global_variables', []),
                'local_variables': file_detail.get('local_variables', []),
                'execution_scope_variables': file_detail.get('execution_scope_variables', []),
                'tables': file_detail.get('tables', []),
                'relationships': file_detail.get('relationships', []),
                'language': file_detail.get('language', 'python')
            }
            
            # Generate diagrams for this file
            diagram_gen = DiagramGenerator(single_file_result)
            
            # 1. Generate Architecture Diagram for this file
            architecture_diagram = diagram_gen.generate_architecture_diagram()
            
            # 2. Generate Structure Diagram for this file
            structure_diagram = diagram_gen.generate_structure_diagram()
            
            # 3. Generate Sequence Diagram for this file's function interactions
            sequence_diagram = diagram_gen.generate_sequence_diagram()
            
            # 4. Generate Dependencies Diagram for this file
            dependencies_diagram = diagram_gen.generate_dependency_diagram()
            
            # 5. Generate Flowchart per top-level function or class method
            flowcharts = {}
            
            # Get top-level functions (not nested, not methods)
            top_level_funcs = [f for f in single_file_result['functions'] 
                             if not f.get('is_nested', False) and not f.get('is_method', False)]
            
            # Generate flowchart for each top-level function
            for func in top_level_funcs:
                func_name = func.get('name')
                if func_name:
                    try:
                        flowchart = diagram_gen.generate_flowchart(function_name=func_name)
                        flowcharts[func_name] = flowchart
                    except Exception as e:
                        print(f"Error generating flowchart for {func_name} in {file_path}: {str(e)}")
                        flowcharts[func_name] = None
            
            # Get class methods
            for cls in single_file_result['classes']:
                cls_name = cls.get('name')
                methods = cls.get('methods', [])
                for method in methods:
                    method_name = method.get('name')
                    if method_name:
                        # For methods, control flow entries use "ClassName.method_name" format
                        method_full_name = f"{cls_name}.{method_name}"
                        method_flow = [cf for cf in single_file_result['control_flow'] 
                                     if cf.get('function') == method_name or cf.get('function') == method_full_name]
                        
                        # Always try to generate flowchart for methods, even if no control flow
                        try:
                            # Create a temporary result with just this method
                            method_result = single_file_result.copy()
                            # Add method as a function for diagram generation
                            method_as_func = method.copy()
                            method_result['functions'] = [method_as_func]
                            method_result['control_flow'] = method_flow
                            method_diagram_gen = DiagramGenerator(method_result)
                            flowchart = method_diagram_gen.generate_flowchart(function_name=method_name)
                            flowcharts[f"{cls_name}.{method_name}"] = flowchart
                        except Exception as e:
                            print(f"Error generating flowchart for {cls_name}.{method_name} in {file_path}: {str(e)}")
                            flowcharts[f"{cls_name}.{method_name}"] = None
            
            # Generate a combined flowchart for the file (showing all functions)
            combined_flowchart = diagram_gen.generate_flowchart()
            
            file_diagrams[file_path] = {
                'architecture': architecture_diagram,
                'structure': structure_diagram,
                'sequence': sequence_diagram,
                'dependencies': dependencies_diagram,
                'flowchart': combined_flowchart,
                'flowcharts': flowcharts  # Individual function flowcharts
            }
            
        except Exception as e:
            print(f"Error generating diagrams for {file_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            file_diagrams[file_path] = {
                'architecture': None,
                'structure': None,
                'sequence': None,
                'dependencies': None,
                'flowchart': None,
                'flowcharts': {},
                'error': str(e)
            }
    
    return file_diagrams

def clone_github_repo(repo_url: str) -> str:
    """Clone a GitHub repository to a temporary directory.
    
    Args:
        repo_url: GitHub repository URL (e.g., https://github.com/username/repo)
        
    Returns:
        Local path to the cloned repository
        
    Raises:
        ValueError: If the URL is invalid or cloning fails
        subprocess.CalledProcessError: If git clone command fails
    """
    # Normalize the URL
    url = repo_url.strip()
    
    # Remove trailing .git if present
    if url.endswith('.git'):
        url = url[:-4]
    
    # Handle git@github.com:username/repo format
    if url.startswith('git@github.com:'):
        url = url.replace('git@github.com:', 'https://github.com/')
    
    # Handle github.com/username/repo format (add https://)
    if url.startswith('github.com/'):
        url = 'https://' + url
    
    # Validate GitHub URL pattern
    if not url.startswith('https://github.com/') and not url.startswith('http://github.com/'):
        raise ValueError(f'Invalid GitHub URL format: {repo_url}. Expected: https://github.com/username/repo')
    
    # Extract repo name from URL for the temp directory name
    repo_name = url.split('/')[-1]
    if not repo_name:
        raise ValueError(f'Could not extract repository name from URL: {repo_url}')
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp(prefix='documind_repo_')
    
    try:
        # Clone the repository
        clone_path = os.path.join(temp_dir, repo_name)
        
        # Run git clone command
        result = subprocess.run(
            ['git', 'clone', url, clone_path],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            check=True
        )
        
        # Verify the directory was created and contains files
        # Normalize to absolute path
        clone_path = os.path.abspath(clone_path)
        
        if not os.path.exists(clone_path):
            raise ValueError(f'Repository cloned but directory not found: {clone_path}')
        
        if not os.path.isdir(clone_path):
            raise ValueError(f'Cloned path is not a directory: {clone_path}')
        
        # Verify the directory has content
        try:
            files = os.listdir(clone_path)
            if not files:
                raise ValueError(f'Repository cloned but directory is empty: {clone_path}')
        except OSError as e:
            raise ValueError(f'Cannot access cloned repository directory: {clone_path}. Error: {str(e)}')
        
        return clone_path
        
    except subprocess.TimeoutExpired:
        # Clean up temp directory on timeout
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError(f'Git clone timed out after 5 minutes for repository: {repo_url}')
    
    except subprocess.CalledProcessError as e:
        # Clean up temp directory on error
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise ValueError(f'Failed to clone repository {repo_url}: {error_msg}')
    
    except Exception as e:
        # Clean up temp directory on any other error
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError(f'Error cloning repository {repo_url}: {str(e)}')

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

@app.route('/api/generate-project-docs', methods=['POST'])
def generate_project_documentation():
    """Generate professional documentation for a project."""
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        project_data = data.get('project_data', {})
        
        if not project_data:
            return jsonify({'error': 'No project data provided'}), 400
        
        # Generate documentation for the project
        doc_generator = DocumentationGenerator()
        documentation = doc_generator.generate_project_documentation(project_data)
        
        return jsonify({
            'success': True,
            'documentation': documentation,
            'used_llm': doc_generator.use_llm
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error generating project documentation: {error_details}")
        return jsonify({'error': f'Error generating project documentation: {str(e)}'}), 500

@app.route('/api/parse-project', methods=['POST'])
def parse_project():
    """Parse an entire project folder.
    
    Accepts a local folder path and parses all supported files in the project.
    """
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        folder_path = data.get('folder_path', '').strip()
        
        if not folder_path:
            return jsonify({'error': 'No folder path provided'}), 400
        
        # Use project_scanner to scan and parse the project
        all_results = scan_project(folder_path)
        
        # Generate both per-file diagrams AND full-project diagrams
        try:
            # Generate per-file diagrams for individual file views
            file_diagrams = generate_per_file_diagrams(all_results.get('file_details', []))
            all_results['file_diagrams'] = file_diagrams
            
            # Generate full-project combined diagrams
            diagram_gen = DiagramGenerator(all_results)
            full_project_diagrams = {
                'architecture': diagram_gen.generate_architecture_diagram(),
                'code_architecture': diagram_gen.generate_code_architecture_diagram(),
                'sequence': diagram_gen.generate_sequence_diagram(),
                'dependencies': diagram_gen.generate_dependency_diagram(),
                'flowchart': diagram_gen.generate_flowchart(),
                'structure': diagram_gen.generate_structure_diagram()
            }
            all_results['diagrams'] = full_project_diagrams
        except Exception as diagram_error:
            print(f"Error generating diagrams: {str(diagram_error)}")
            all_results['file_diagrams'] = {}
            all_results['diagrams'] = {}
        
        return jsonify(all_results)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error parsing project: {error_details}")
        return jsonify({'error': f'Error parsing project: {str(e)}'}), 500

@app.route('/api/parse-uploaded-project', methods=['POST'])
def parse_uploaded_project():
    """Parse uploaded project files.
    
    Accepts multiple file uploads and parses them as a project.
    """
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files provided'}), 400
        
        # Supported file extensions
        supported_extensions = {
            '.py', '.pyw', '.pyi',  # Python
            '.js', '.jsx', '.mjs',  # JavaScript
            '.java',                 # Java
            '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx',  # C/C++
            '.php', '.phtml',        # PHP
            '.sql'                   # SQL
        }
        
        # Filter supported files
        supported_files = []
        for file in files:
            if file.filename:
                _, ext = os.path.splitext(file.filename)
                if ext.lower() in supported_extensions:
                    supported_files.append(file)
        
        if not supported_files:
            return jsonify({'error': 'No supported files found. Supported extensions: .py, .js, .jsx, .java, .c, .cpp, .php, .sql'}), 400
        
        # Initialize aggregated results (similar to scan_project)
        aggregated = {
            'files': [],
            'file_details': [],
            'summary': {
                'total_files': len(supported_files),
                'total_lines': 0,
                'total_functions': 0,
                'sync_functions': 0,
                'async_functions': 0,
                'nested_functions': 0,
                'total_classes': 0,
                'total_methods': 0,
                'total_variables': 0,
                'global_variables': 0,
                'local_variables': 0,
                'execution_scope_variables': 0,
                'class_variables': 0,
                'instance_variables': 0,
                'total_decorators': 0,
                'total_imports': 0,
                'total_tables': 0,
                'total_relationships': 0
            },
            'functions': [],
            'classes': [],
            'global_variables': [],
            'local_variables': [],
            'execution_scope_variables': [],
            'imports': [],
            'decorators': [],
            'function_calls': [],
            'method_calls': [],
            'class_instantiations': [],
            'control_flow': [],
            'warnings': [],
            'import_usage': [],
            'tables': [],
            'relationships': [],
            'language': 'mixed',
            'project_path': 'uploaded_files'
        }
        
        # Parse each uploaded file
        for file in supported_files:
            try:
                # Read file content
                code = file.read().decode('utf-8', errors='ignore')
                
                # Get file path (use webkitRelativePath if available, otherwise filename)
                file_path = file.filename
                if hasattr(file, 'webkitRelativePath') and file.webkitRelativePath:
                    file_path = file.webkitRelativePath
                
                # Detect language
                detected_language = LanguageDetector.detect(filename=file_path, code=code)
                lang_normalized = (detected_language or 'python').lower()
                
                # Parse file (parse_code_auto already normalizes variables for Python)
                result = parse_code_auto(code, lang_normalized)
                
                # Calculate lines of code
                lines_of_code = len(code.split('\n'))
                
                # Store file information
                file_info = {
                    'path': file_path,
                    'absolute_path': file_path,
                    'language': lang_normalized,
                    'functions_count': len(result.get('functions', [])),
                    'classes_count': len(result.get('classes', [])),
                    'tables_count': len(result.get('tables', [])),
                    'imports_count': len(result.get('imports', [])),
                    'lines_of_code': lines_of_code
                }
                aggregated['files'].append(file_info)
                
                # Store full parsed result for this file
                file_detail = {
                    'path': file_path,
                    'absolute_path': file_path,
                    'language': lang_normalized,
                    'functions': result.get('functions', []),
                    'classes': result.get('classes', []),
                    'tables': result.get('tables', []),
                    'relationships': result.get('relationships', []),
                    'global_variables': result.get('global_variables', []),
                    'local_variables': result.get('local_variables', []),
                    'execution_scope_variables': result.get('execution_scope_variables', []),
                    'imports': result.get('imports', []),
                    'decorators': result.get('decorators', []),
                    'function_calls': result.get('function_calls', []),
                    'method_calls': result.get('method_calls', []),
                    'class_instantiations': result.get('class_instantiations', []),
                    'control_flow': result.get('control_flow', []),
                    'warnings': result.get('warnings', []),
                    'summary': result.get('summary', {})
                }
                aggregated['file_details'].append(file_detail)
                
                # Aggregate summary statistics
                summary = result.get('summary', {})
                aggregated['summary']['total_lines'] += lines_of_code
                aggregated['summary']['total_functions'] += summary.get('total_functions', 0)
                aggregated['summary']['sync_functions'] += summary.get('sync_functions', 0)
                aggregated['summary']['async_functions'] += summary.get('async_functions', 0)
                aggregated['summary']['nested_functions'] += summary.get('nested_functions', 0)
                aggregated['summary']['total_classes'] += summary.get('total_classes', 0)
                aggregated['summary']['total_methods'] += summary.get('total_methods', 0)
                aggregated['summary']['global_variables'] += summary.get('global_variables', 0)
                aggregated['summary']['local_variables'] += summary.get('local_variables', 0)
                aggregated['summary']['execution_scope_variables'] += summary.get('execution_scope_variables', 0)
                aggregated['summary']['class_variables'] += summary.get('class_variables', 0)
                aggregated['summary']['instance_variables'] += summary.get('instance_variables', 0)
                aggregated['summary']['total_decorators'] += summary.get('total_decorators', 0)
                aggregated['summary']['total_imports'] += summary.get('total_imports', 0)
                aggregated['summary']['total_tables'] += summary.get('total_tables', 0)
                aggregated['summary']['total_relationships'] += summary.get('total_relationships', 0)
                
                # Merge lists with file context
                for func in result.get('functions', []):
                    func_with_context = func.copy()
                    func_with_context['file'] = file_path
                    aggregated['functions'].append(func_with_context)
                
                for cls in result.get('classes', []):
                    cls_with_context = cls.copy()
                    cls_with_context['file'] = file_path
                    aggregated['classes'].append(cls_with_context)
                
                # Add file context to variables
                for var in result.get('global_variables', []):
                    var_with_context = var.copy()
                    var_with_context['file'] = file_path
                    aggregated['global_variables'].append(var_with_context)
                
                for var in result.get('local_variables', []):
                    var_with_context = var.copy()
                    var_with_context['file'] = file_path
                    aggregated['local_variables'].append(var_with_context)
                
                for var in result.get('execution_scope_variables', []):
                    var_with_context = var.copy()
                    var_with_context['file'] = file_path
                    aggregated['execution_scope_variables'].append(var_with_context)
                
                # Merge other lists
                aggregated['imports'].extend(result.get('imports', []))
                aggregated['decorators'].extend(result.get('decorators', []))
                aggregated['function_calls'].extend(result.get('function_calls', []))
                aggregated['method_calls'].extend(result.get('method_calls', []))
                aggregated['class_instantiations'].extend(result.get('class_instantiations', []))
                aggregated['control_flow'].extend(result.get('control_flow', []))
                aggregated['warnings'].extend(result.get('warnings', []))
                aggregated['import_usage'].extend(result.get('import_usage', []))
                aggregated['tables'].extend(result.get('tables', []))
                aggregated['relationships'].extend(result.get('relationships', []))
                
            except Exception as e:
                # Skip files that can't be parsed, but log the error
                print(f"Error parsing uploaded file {file.filename}: {str(e)}")
                file_path = file.filename
                aggregated['files'].append({
                    'path': file_path,
                    'absolute_path': file_path,
                    'language': 'unknown',
                    'functions_count': 0,
                    'classes_count': 0,
                    'tables_count': 0,
                    'imports_count': 0,
                    'lines_of_code': 0,
                    'error': str(e)
                })
                aggregated['file_details'].append({
                    'path': file_path,
                    'absolute_path': file_path,
                    'language': 'unknown',
                    'functions': [],
                    'classes': [],
                    'tables': [],
                    'relationships': [],
                    'global_variables': [],
                    'local_variables': [],
                    'execution_scope_variables': [],
                    'imports': [],
                    'decorators': [],
                    'function_calls': [],
                    'method_calls': [],
                    'class_instantiations': [],
                    'control_flow': [],
                    'warnings': [{'type': 'error', 'message': str(e)}],
                    'summary': {},
                    'error': str(e)
                })
                continue
        
        # Calculate total variables after processing all files
        aggregated['summary']['total_variables'] = (
            aggregated['summary']['global_variables'] +
            aggregated['summary']['local_variables'] +
            aggregated['summary']['execution_scope_variables'] +
            aggregated['summary']['class_variables'] +
            aggregated['summary']['instance_variables']
        )
        
        # Generate both per-file diagrams AND full-project diagrams
        try:
            # Generate per-file diagrams for individual file views
            file_diagrams = generate_per_file_diagrams(aggregated.get('file_details', []))
            aggregated['file_diagrams'] = file_diagrams
            
            # Generate full-project combined diagrams
            diagram_gen = DiagramGenerator(aggregated)
            full_project_diagrams = {
                'architecture': diagram_gen.generate_architecture_diagram(),
                'code_architecture': diagram_gen.generate_code_architecture_diagram(),
                'sequence': diagram_gen.generate_sequence_diagram(),
                'dependencies': diagram_gen.generate_dependency_diagram(),
                'flowchart': diagram_gen.generate_flowchart(),
                'structure': diagram_gen.generate_structure_diagram()
            }
            aggregated['diagrams'] = full_project_diagrams
        except Exception as diagram_error:
            print(f"Error generating diagrams: {str(diagram_error)}")
            aggregated['file_diagrams'] = {}
            aggregated['diagrams'] = {}
        
        return jsonify(aggregated)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error parsing uploaded project: {error_details}")
        return jsonify({'error': f'Error parsing uploaded project: {str(e)}'}), 500

@app.route('/api/parse-github-repo', methods=['POST'])
def parse_github_repo():
    """Clone a GitHub repository and parse it.
    
    Accepts a GitHub repository URL, clones it to a temporary directory,
    and parses all supported files in the project.
    """
    clone_path = None
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        repo_url = data.get('repo_url', '').strip()
        
        if not repo_url:
            return jsonify({'error': 'No GitHub repository URL provided'}), 400
        
        # Clone the GitHub repository to a temporary directory
        try:
            clone_path = clone_github_repo(repo_url)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            # Catch any other exceptions from clone_github_repo
            error_msg = str(e)
            if not error_msg:
                error_msg = 'Failed to clone repository. Please check the URL and try again.'
            return jsonify({'error': f'Error cloning repository: {error_msg}'}), 500
        
        # Verify clone_path exists before scanning
        if not clone_path or not os.path.exists(clone_path):
            error_msg = f'Repository cloned but path does not exist: {clone_path}'
            if clone_path:
                parent_dir = os.path.dirname(clone_path)
                if os.path.exists(parent_dir):
                    shutil.rmtree(parent_dir, ignore_errors=True)
            return jsonify({'error': error_msg}), 500
        
        # Normalize the path to absolute path
        clone_path = os.path.abspath(clone_path)
        
        # Use project_scanner to scan and parse the cloned project
        try:
            all_results = scan_project(clone_path)
        except ValueError as e:
            # Clean up cloned directory on validation error
            if clone_path and os.path.exists(clone_path):
                parent_dir = os.path.dirname(clone_path)
                if os.path.exists(parent_dir):
                    shutil.rmtree(parent_dir, ignore_errors=True)
            error_msg = str(e)
            # Provide more helpful error message
            if 'Path does not exist' in error_msg:
                error_msg = f'Cloned repository path not found. This may be a temporary issue. Please try again. Original error: {error_msg}'
            return jsonify({'error': error_msg}), 400
        except Exception as scan_error:
            # Clean up cloned directory on scan error
            if clone_path and os.path.exists(clone_path):
                parent_dir = os.path.dirname(clone_path)
                if os.path.exists(parent_dir):
                    shutil.rmtree(parent_dir, ignore_errors=True)
            error_msg = str(scan_error)
            if not error_msg:
                error_msg = 'Failed to scan and parse the cloned repository.'
            # Provide more helpful error message
            if 'Path does not exist' in error_msg or 'does not exist' in error_msg.lower():
                error_msg = f'Repository path issue detected. Please try again. Original error: {error_msg}'
            return jsonify({'error': f'Error scanning repository: {error_msg}'}), 500
        
        # Extract detected languages from file extensions
        detected_languages = set()
        language_map = {
            '.py': 'Python', '.pyw': 'Python', '.pyi': 'Python',
            '.js': 'JavaScript', '.jsx': 'JavaScript', '.mjs': 'JavaScript',
            '.java': 'Java',
            '.c': 'C', '.cpp': 'C++', '.cc': 'C++', '.cxx': 'C++',
            '.h': 'C/C++', '.hpp': 'C++', '.hxx': 'C++',
            '.php': 'PHP', '.phtml': 'PHP',
            '.sql': 'SQL'
        }
        
        if 'files' in all_results:
            for file_info in all_results['files']:
                file_path = file_info.get('absolute_path') or file_info.get('path', '')
                if file_path:
                    _, ext = os.path.splitext(file_path)
                    lang = language_map.get(ext.lower())
                    if lang:
                        detected_languages.add(lang)
        
        # Generate both per-file diagrams AND full-project diagrams
        try:
            # Generate per-file diagrams for individual file views
            file_diagrams = generate_per_file_diagrams(all_results.get('file_details', []))
            all_results['file_diagrams'] = file_diagrams
            
            # Generate full-project combined diagrams
            diagram_gen = DiagramGenerator(all_results)
            full_project_diagrams = {
                'architecture': diagram_gen.generate_architecture_diagram(),
                'code_architecture': diagram_gen.generate_code_architecture_diagram(),
                'sequence': diagram_gen.generate_sequence_diagram(),
                'dependencies': diagram_gen.generate_dependency_diagram(),
                'flowchart': diagram_gen.generate_flowchart(),
                'structure': diagram_gen.generate_structure_diagram()
            }
            all_results['diagrams'] = full_project_diagrams
        except Exception as diagram_error:
            # Log error but don't fail the request
            print(f"Error generating diagrams: {str(diagram_error)}")
            all_results['file_diagrams'] = {}
            all_results['diagrams'] = {}
        
        # Add metadata about the cloned repository
        all_results['github_repo_url'] = repo_url
        all_results['cloned_path'] = clone_path
        all_results['detected_languages'] = sorted(list(detected_languages))
        
        # Note: We don't clean up the temp directory here to allow for potential
        # re-analysis. The OS will clean it up eventually, or it can be cleaned
        # in a background task if needed.
        
        return jsonify(all_results)
        
    except ValueError as e:
        # Clean up on validation errors
        if clone_path and os.path.exists(clone_path):
            parent_dir = os.path.dirname(clone_path)
            if os.path.exists(parent_dir):
                shutil.rmtree(parent_dir, ignore_errors=True)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # Clean up on any other errors
        if clone_path and os.path.exists(clone_path):
            parent_dir = os.path.dirname(clone_path)
            if os.path.exists(parent_dir):
                shutil.rmtree(parent_dir, ignore_errors=True)
        # Return user-friendly error message instead of traceback
        error_msg = str(e)
        if not error_msg:
            error_msg = 'An unexpected error occurred while processing the repository.'
        return jsonify({'error': error_msg}), 500

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

