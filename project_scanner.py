"""
Project scanner module for parsing entire project folders.
Scans directories, collects files by extension, and parses them.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Set
from language_detector import LanguageDetector
from code_parser import CodeParser
from javascript_parser import JavaScriptParser
from sql_parser import SQLParser


def _parse_code_auto(code: str, language: str) -> dict:
    """Parse code automatically based on detected language.
    
    This is a local copy to avoid circular imports.
    
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
        # Note: normalize_variable_fields is handled in app.py for single file parsing
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


def scan_project(root_path: str) -> Dict[str, Any]:
    """Scan a project folder and parse all supported files.
    
    Args:
        root_path: Absolute path to the project folder
        
    Returns:
        Dictionary containing:
        - files: List of parsed file information
        - summary: Aggregated summary statistics
        - functions: All functions from all files
        - classes: All classes from all files
        - tables: All tables from all files (SQL)
        - relationships: All relationships from all files (SQL)
        - And other aggregated data structures
    """
    # Validate path
    if not os.path.exists(root_path):
        raise ValueError(f'Path does not exist: {root_path}')
    
    if not os.path.isdir(root_path):
        raise ValueError(f'Path is not a directory: {root_path}')
    
    # Supported file extensions
    supported_extensions = {
        '.py', '.pyw', '.pyi',  # Python
        '.js', '.jsx', '.mjs',  # JavaScript
        '.java',                 # Java
        '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx',  # C/C++
        '.php', '.phtml',        # PHP
        '.sql'                   # SQL
    }
    
    # Directories to skip
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env', '.env', 
                 'dist', 'build', '.pytest_cache', '.mypy_cache', '.idea', '.vscode',
                 'target', 'bin', 'obj', '.vs', 'coverage', '.coverage'}
    
    # Collect all supported files
    project_files = []
    for root, dirs, files in os.walk(root_path):
        # Filter out directories to skip
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            
            if ext.lower() in supported_extensions:
                project_files.append(file_path)
    
    if not project_files:
        return {
            'files': [],
            'file_details': [],
            'summary': {
                'total_files': 0,
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
            'project_path': root_path
        }
    
    # Initialize aggregated results
    aggregated = {
        'files': [],
        'file_details': [],  # Store full parsed results for each file
        'summary': {
            'total_files': len(project_files),
            'total_lines': 0,
            'total_functions': 0,
            'sync_functions': 0,
            'async_functions': 0,
            'nested_functions': 0,
            'total_classes': 0,
            'total_methods': 0,
            'total_variables': 0,  # Aggregated total of all variable types
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
        'project_path': root_path
    }
    
    # Parse each file
    for file_path in project_files:
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            
            # Detect language by extension
            detected_language = LanguageDetector.detect(filename=file_path, code=code)
            lang_normalized = (detected_language or 'python').lower()
            
            # Parse file
            result = _parse_code_auto(code, lang_normalized)
            
            # Get relative path
            relative_path = os.path.relpath(file_path, root_path)
            
            # Calculate lines of code for this file
            lines_of_code = len(code.split('\n'))
            
            # Store file information
            file_info = {
                'path': relative_path,
                'absolute_path': file_path,
                'language': lang_normalized,
                'functions_count': len(result.get('functions', [])),
                'classes_count': len(result.get('classes', [])),
                'tables_count': len(result.get('tables', [])),
                'imports_count': len(result.get('imports', [])),
                'lines_of_code': lines_of_code
            }
            aggregated['files'].append(file_info)
            
            # Aggregate total lines
            aggregated['summary']['total_lines'] += lines_of_code
            
            # Store full parsed result for this file
            file_detail = {
                'path': relative_path,
                'absolute_path': file_path,
                'language': lang_normalized,
                'lines_of_code': lines_of_code,
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
                func_with_context['file'] = relative_path
                aggregated['functions'].append(func_with_context)
            
            for cls in result.get('classes', []):
                cls_with_context = cls.copy()
                cls_with_context['file'] = relative_path
                aggregated['classes'].append(cls_with_context)
            
            # Add file context to variables
            for var in result.get('global_variables', []):
                var_with_context = var.copy()
                var_with_context['file'] = relative_path
                aggregated['global_variables'].append(var_with_context)
            
            for var in result.get('local_variables', []):
                var_with_context = var.copy()
                var_with_context['file'] = relative_path
                aggregated['local_variables'].append(var_with_context)
            
            for var in result.get('execution_scope_variables', []):
                var_with_context = var.copy()
                var_with_context['file'] = relative_path
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
            print(f"Error parsing {file_path}: {str(e)}")
            # Still add file info but mark as error
            relative_path = os.path.relpath(file_path, root_path)
            file_info = {
                'path': relative_path,
                'absolute_path': file_path,
                'language': 'unknown',
                'functions_count': 0,
                'classes_count': 0,
                'tables_count': 0,
                'imports_count': 0,
                'lines_of_code': 0,
                'error': str(e)
            }
            aggregated['files'].append(file_info)
            
            # Add empty file detail with error
            aggregated['file_details'].append({
                'path': relative_path,
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
    
    # Calculate total variables (sum of all variable types) after processing all files
    aggregated['summary']['total_variables'] = (
        aggregated['summary']['global_variables'] +
        aggregated['summary']['local_variables'] +
        aggregated['summary']['execution_scope_variables'] +
        aggregated['summary']['class_variables'] +
        aggregated['summary']['instance_variables']
    )
    
    return aggregated

