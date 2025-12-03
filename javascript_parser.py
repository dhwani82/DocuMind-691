"""
JavaScript code parser using regex-based approach.
Extracts functions, classes, and basic structure from JavaScript code.
Supports JSX syntax and React functional components.
"""

import re
from typing import Dict, List, Any


class JavaScriptParser:
    """Parse JavaScript code to extract structure."""
    
    def __init__(self):
        self.functions = []
        self.classes = []
        self.imports = []
        self.global_vars = []
        self.local_vars = []
        self.execution_scope_vars = []
        self.decorators = []
        self.function_calls = []
        self.method_calls = []
        self.class_instantiations = []
        self.control_flow = []
        self.warnings = []
        self.import_usage = []
    
    def parse(self, code: str) -> Dict[str, Any]:
        """Parse JavaScript code and extract structure.
        
        Args:
            code: JavaScript source code (can include JSX)
            
        Returns:
            Dictionary with parsed structure
        """
        lines = code.split('\n')
        
        # Reset state
        self.functions = []
        self.classes = []
        self.imports = []
        self.global_vars = []
        self.local_vars = []
        self.execution_scope_vars = []
        self.decorators = []
        self.function_calls = []
        self.method_calls = []
        self.class_instantiations = []
        self.control_flow = []
        self.warnings = []
        self.import_usage = []
        
        # Extract imports
        self._extract_imports(code)
        
        # Extract functions (function declarations, arrow functions, methods, React components)
        self._extract_functions(code, lines)
        
        # Extract classes
        self._extract_classes(code, lines)
        
        # Count functions by type
        sync_functions = [f for f in self.functions if not f.get('is_async', False) and not f.get('is_nested', False)]
        async_functions = [f for f in self.functions if f.get('is_async', False) and not f.get('is_nested', False)]
        nested_functions = [f for f in self.functions if f.get('is_nested', False)]
        
        # Count methods
        methods = []
        for cls in self.classes:
            methods.extend(cls.get('methods', []))
        
        # Count variables
        class_vars = []
        instance_vars = []
        for cls in self.classes:
            class_vars.extend(cls.get('class_variables', []))
            instance_vars.extend(cls.get('instance_variables', []))
        
        return {
            'summary': {
                'total_functions': len(self.functions),
                'sync_functions': len(sync_functions),
                'async_functions': len(async_functions),
                'nested_functions': len(nested_functions),
                'total_classes': len(self.classes),
                'total_methods': len(methods),
                'global_variables': len(self.global_vars),
                'local_variables': len(self.local_vars),
                'execution_scope_variables': len(self.execution_scope_vars),
                'class_variables': len(class_vars),
                'instance_variables': len(instance_vars),
                'total_decorators': len(self.decorators),
                'total_imports': len(self.imports)
            },
            'functions': self.functions,
            'classes': self.classes,
            'global_variables': self.global_vars,
            'local_variables': self.local_vars,
            'execution_scope_variables': self.execution_scope_vars,
            'imports': self.imports,
            'decorators': self.decorators,
            'function_calls': self.function_calls,
            'method_calls': self.method_calls,
            'class_instantiations': self.class_instantiations,
            'control_flow': self.control_flow,
            'warnings': self.warnings,
            'import_usage': self.import_usage,
            'language': 'javascript'
        }
    
    def _extract_react_components(self, code: str, lines: List[str]):
        """Extract React functional components (common in JSX files).
        
        React components are often defined as:
        - function ComponentName() { return <JSX>; }
        - const ComponentName = () => { return <JSX>; }
        - export default function ComponentName() { ... }
        
        Args:
            code: JavaScript/JSX source code
            lines: List of code lines
        """
        # React functional components: function ComponentName() { ... }
        # Component names typically start with uppercase
        react_func_pattern = r'(?:export\s+(?:default\s+)?)?function\s+([A-Z][A-Za-z0-9]*)\s*\(([^)]*)\)\s*\{'
        for match in re.finditer(react_func_pattern, code):
            component_name = match.group(1)
            line_num = code[:match.start()].count('\n') + 1
            
            # Extract parameters
            param_str = match.group(2).strip()
            params = [p.strip() for p in param_str.split(',')] if param_str else []
            
            # Check if this component is already in functions list
            if not any(f['name'] == component_name and f['line'] == line_num for f in self.functions):
                self.functions.append({
                    'name': component_name,
                    'line': line_num,
                    'parameters': params,
                    'is_async': False,
                    'is_nested': False,
                    'decorators': [],
                    'returns': None,
                    'docstring': None,
                    'is_react_component': True
                })
        
        # React arrow function components: const ComponentName = () => { ... }
        react_arrow_pattern = r'(?:export\s+(?:default\s+)?)?(?:const|let|var)\s+([A-Z][A-Za-z0-9]*)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>'
        for match in re.finditer(react_arrow_pattern, code):
            component_name = match.group(1)
            line_num = code[:match.start()].count('\n') + 1
            is_async = 'async' in match.group(0)
            
            param_str = match.group(2).strip()
            params = [p.strip() for p in param_str.split(',')] if param_str else []
            
            # Check if this component is already in functions list
            if not any(f['name'] == component_name and f['line'] == line_num for f in self.functions):
                self.functions.append({
                    'name': component_name,
                    'line': line_num,
                    'parameters': params,
                    'is_async': is_async,
                    'is_nested': False,
                    'decorators': [],
                    'returns': None,
                    'docstring': None,
                    'is_react_component': True
                })
    
    def _extract_imports(self, code: str):
        """Extract import statements."""
        # ES6 imports: import ... from '...'
        # Pattern 1: import { name1, name2 } from 'module'
        named_import_pattern = r'import\s+\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(named_import_pattern, code):
            module = match.group(2)
            names_str = match.group(1)
            # Parse individual names (handle "name as alias")
            for name_part in names_str.split(','):
                name_part = name_part.strip()
                if ' as ' in name_part:
                    name, alias = name_part.split(' as ', 1)
                    name, alias = name.strip(), alias.strip()
                else:
                    name, alias = name_part.strip(), None
                
                self.imports.append({
                    'type': 'from_import',
                    'module': module,
                    'name': name,
                    'alias': alias,
                    'line': code[:match.start()].count('\n') + 1
                })
        
        # Pattern 2: import * as alias from 'module'
        namespace_import_pattern = r'import\s+\*\s+as\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(namespace_import_pattern, code):
            alias = match.group(1)
            module = match.group(2)
            self.imports.append({
                'type': 'from_import',
                'module': module,
                'name': '*',
                'alias': alias,
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Pattern 3: import defaultName from 'module'
        default_import_pattern = r'import\s+(\w+)(?:\s+from)?\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(default_import_pattern, code):
            # Skip if it's part of a named import or namespace import (already handled)
            if '{' in match.group(0) or '* as' in match.group(0):
                continue
            name = match.group(1)
            module = match.group(2)
            self.imports.append({
                'type': 'from_import',
                'module': module,
                'name': name,
                'alias': None,
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Pattern 4: import 'module' (side-effect import)
        side_effect_pattern = r'import\s+[\'"]([^\'"]+)[\'"]\s*(?!from)'
        for match in re.finditer(side_effect_pattern, code):
            module = match.group(1)
            self.imports.append({
                'type': 'import',
                'module': module,
                'name': None,
                'alias': None,
                'line': code[:match.start()].count('\n') + 1
            })
        
        # require() statements
        require_pattern = r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
        for match in re.finditer(require_pattern, code):
            module = match.group(1)
            self.imports.append({
                'type': 'require',
                'module': module,
                'name': None,
                'alias': None,
                'line': code[:match.start()].count('\n') + 1
            })
    
    def _extract_functions(self, code: str, lines: List[str]):
        """Extract function declarations and arrow functions.
        
        Also extracts React components (functions/components starting with uppercase).
        """
        # Function declarations: function name(...) { ... }
        # Exclude React components (uppercase) - they'll be handled separately
        func_pattern = r'function\s+([a-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{'
        for match in re.finditer(func_pattern, code):
            func_name = match.group(1)
            line_num = code[:match.start()].count('\n') + 1
            
            # Extract parameters
            params_match = re.search(r'function\s+\w+\s*\(([^)]*)\)', match.group(0))
            params = []
            if params_match:
                param_str = params_match.group(1).strip()
                if param_str:
                    params = [p.strip() for p in param_str.split(',')]
            
            self.functions.append({
                'name': func_name,
                'line': line_num,
                'parameters': params,
                'is_async': False,
                'is_nested': False,
                'decorators': [],
                'returns': None,
                'docstring': None
            })
        
        # Arrow functions: const name = (...) => { ... } or const name = async (...) => { ... }
        # Exclude React components (uppercase) - they'll be handled separately
        arrow_pattern = r'(?:const|let|var)\s+([a-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>'
        for match in re.finditer(arrow_pattern, code):
            func_name = match.group(1)
            line_num = code[:match.start()].count('\n') + 1
            is_async = 'async' in match.group(0)
            
            param_str = match.group(2).strip()
            params = []
            if param_str:
                params = [p.strip() for p in param_str.split(',')]
            
            self.functions.append({
                'name': func_name,
                'line': line_num,
                'parameters': params,
                'is_async': is_async,
                'is_nested': False,
                'decorators': [],
                'returns': None,
                'docstring': None
            })
        
        # Extract React components (functions/components starting with uppercase)
        self._extract_react_components(code, lines)
    
    def _extract_classes(self, code: str, lines: List[str]):
        """Extract class declarations."""
        # Class declarations: class Name { ... }
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{'
        for match in re.finditer(class_pattern, code):
            class_name = match.group(1)
            base_class = match.group(2) if match.group(2) else None
            line_num = code[:match.start()].count('\n') + 1
            
            # Extract methods (simplified - looks for method definitions in class)
            methods = []
            class_start = match.end()
            # Find matching closing brace
            brace_count = 1
            i = class_start
            while i < len(code) and brace_count > 0:
                if code[i] == '{':
                    brace_count += 1
                elif code[i] == '}':
                    brace_count -= 1
                i += 1
            
            class_body = code[class_start:i-1]
            
            # Extract methods: methodName(...) { or methodName = (...) => {
            method_pattern = r'(\w+)\s*(?:\(([^)]*)\)\s*\{|=\s*(?:async\s+)?\(([^)]*)\)\s*=>)'
            for method_match in re.finditer(method_pattern, class_body):
                method_name = method_match.group(1)
                if method_name not in ['constructor', 'get', 'set']:  # Skip special methods for now
                    param_str = method_match.group(2) or method_match.group(3) or ''
                    params = [p.strip() for p in param_str.split(',')] if param_str.strip() else []
                    methods.append({
                        'name': method_name,
                        'parameters': params,
                        'line': code[:class_start + method_match.start()].count('\n') + 1
                    })
            
            self.classes.append({
                'name': class_name,
                'line': line_num,
                'bases': [base_class] if base_class else [],
                'decorators': [],
                'methods': methods,
                'class_variables': [],
                'instance_variables': []
            })

