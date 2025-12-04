import ast
from typing import Dict, List, Any
from collections import defaultdict

class CodeParser:
    def __init__(self):
        self.functions = []
        self.classes = []
        self.global_vars = []
        self.local_vars = []  # Track local variables in functions/methods
        self.execution_scope_vars = []  # Track variables in if __name__ == "__main__" blocks
        self.imports = []
        self.decorators = []
        self.function_calls = []  # Track function calls: (caller, callee, line)
        self.method_calls = []  # Track method calls: (caller_class, method, line)
        self.class_instantiations = []  # Track class instantiations: (caller, class_name, line)
        self.control_flow = []  # Track control flow structures for flowcharts
        self.warnings = []  # Track code warnings (shadowed variables, duplicates, etc.)
        self.global_declarations = {}  # Track global declarations per function
        self.nonlocal_declarations = {}  # Track nonlocal declarations per function
        self.import_usage = []  # Track which classes/functions use which imports: (entity, import_module, line)
        
    def parse(self, code: str) -> Dict[str, Any]:
        """Parse Python code and extract all relevant information."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise e
        
        # Reset state
        self.functions = []
        self.classes = []
        self.global_vars = []
        self.local_vars = []
        self.execution_scope_vars = []
        self.imports = []
        self.decorators = []
        self.function_calls = []
        self.method_calls = []
        self.class_instantiations = []
        self.control_flow = []
        self.warnings = []
        self.global_declarations = {}
        self.nonlocal_declarations = {}
        self.import_usage = []
        
        # Visit all nodes
        visitor = CodeVisitor(self)
        visitor.visit(tree)
        
        # Detect warnings after parsing
        self._detect_warnings()
        
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
            'import_usage': self.import_usage
        }
    
    def _detect_warnings(self):
        """Detect code warnings: shadowed variables, duplicates, global overrides."""
        # Get all global variable names
        global_names = {v['name']: v for v in self.global_vars}
        
        # Track warnings to avoid duplicates
        warning_keys = set()
        
        # Check for shadowed variables and global overrides
        for local_var in self.local_vars:
            var_name = local_var['name']
            func_name = local_var['function']
            
            if var_name in global_names:
                # Check if it's declared as global in this function
                is_declared_global = (
                    func_name in self.global_declarations and 
                    var_name in self.global_declarations[func_name]
                )
                
                if not is_declared_global:
                    # This is a shadowed variable / global override
                    warning_key = f'shadow_{func_name}_{var_name}'
                    if warning_key not in warning_keys:
                        warning_keys.add(warning_key)
                        self.warnings.append({
                            'type': 'global_override',
                            'severity': 'warning',
                            'message': f'Variable "{var_name}" in {func_name} shadows global variable (consider using "global {var_name}")',
                            'variable': var_name,
                            'line': local_var['line'],
                            'function': func_name,
                            'global_line': global_names[var_name]['line']
                        })
        
        # Check for duplicate function names
        function_names = {}
        for func in self.functions:
            func_name = func['name']
            if func_name in function_names:
                self.warnings.append({
                    'type': 'duplicate_function',
                    'severity': 'warning',
                    'message': f'Duplicate function name "{func_name}"',
                    'name': func_name,
                    'line': func['line'],
                    'previous_line': function_names[func_name]['line']
                })
            else:
                function_names[func_name] = func
        
        # Check for duplicate class names
        class_names = {}
        for cls in self.classes:
            cls_name = cls['name']
            if cls_name in class_names:
                self.warnings.append({
                    'type': 'duplicate_class',
                    'severity': 'warning',
                    'message': f'Duplicate class name "{cls_name}"',
                    'name': cls_name,
                    'line': cls['line'],
                    'previous_line': class_names[cls_name]['line']
                })
            else:
                class_names[cls_name] = cls
        
        # Check for duplicate variable names in same scope
        # Group local variables by function
        local_by_function = {}
        for local_var in self.local_vars:
            func_name = local_var['function']
            if func_name not in local_by_function:
                local_by_function[func_name] = {}
            var_name = local_var['name']
            if var_name in local_by_function[func_name]:
                self.warnings.append({
                    'type': 'duplicate_variable',
                    'severity': 'info',
                    'message': f'Variable "{var_name}" defined multiple times in {func_name}',
                    'variable': var_name,
                    'line': local_var['line'],
                    'function': func_name,
                    'previous_line': local_by_function[func_name][var_name]['line']
                })
            else:
                local_by_function[func_name][var_name] = local_var
        


class CodeVisitor(ast.NodeVisitor):
    def __init__(self, parser: CodeParser):
        self.parser = parser
        self.current_class = None
        self.current_function = None
        self.nesting_level = 0
        self.inside_method = False
        self.inside_name_main = False  # Track if we're inside if __name__ == "__main__"
        self.node_counter = 0  # For unique node IDs in flowcharts
        
    def visit_FunctionDef(self, node):
        """Visit function definitions."""
        is_nested = self.nesting_level > 0 or self.current_class is not None
        
        func_info = {
            'name': node.name,
            'line': node.lineno,
            'is_async': False,
            'is_nested': is_nested,
            'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
            'parameters': [arg.arg for arg in node.args.args],
            'returns': self._get_return_annotation(node.returns) if node.returns else None,
            'docstring': self._get_docstring(node.body)
        }
        
        # Check for decorators
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name not in [d['name'] for d in self.parser.decorators]:
                self.parser.decorators.append({
                    'name': decorator_name,
                    'line': decorator.lineno if hasattr(decorator, 'lineno') else None
                })
        
        if self.current_class:
            # This is a method
            if 'methods' not in self.current_class:
                self.current_class['methods'] = []
            self.current_class['methods'].append(func_info)
            # Mark that we're inside a method
            prev_inside_method = self.inside_method
            prev_function = self.current_function
            self.inside_method = True
            self.current_function = f"{self.current_class['name']}.{node.name}"
            self.nesting_level += 1
            self.generic_visit(node)
            self.nesting_level -= 1
            self.inside_method = prev_inside_method
            self.current_function = prev_function
        else:
            # This is a function
            self.parser.functions.append(func_info)
            prev_function = self.current_function
            self.current_function = node.name
            # Visit nested functions
            self.nesting_level += 1
            self.generic_visit(node)
            self.nesting_level -= 1
            self.current_function = prev_function
    
    def visit_AsyncFunctionDef(self, node):
        """Visit async function definitions."""
        is_nested = self.nesting_level > 0 or self.current_class is not None
        
        func_info = {
            'name': node.name,
            'line': node.lineno,
            'is_async': True,
            'is_nested': is_nested,
            'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
            'parameters': [arg.arg for arg in node.args.args],
            'returns': self._get_return_annotation(node.returns) if node.returns else None,
            'docstring': self._get_docstring(node.body)
        }
        
        # Check for decorators
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name not in [d['name'] for d in self.parser.decorators]:
                self.parser.decorators.append({
                    'name': decorator_name,
                    'line': decorator.lineno if hasattr(decorator, 'lineno') else None
                })
        
        if self.current_class:
            # This is an async method
            if 'methods' not in self.current_class:
                self.current_class['methods'] = []
            self.current_class['methods'].append(func_info)
            # Mark that we're inside a method
            prev_inside_method = self.inside_method
            prev_function = self.current_function
            self.inside_method = True
            self.current_function = f"{self.current_class['name']}.{node.name}"
            self.nesting_level += 1
            self.generic_visit(node)
            self.nesting_level -= 1
            self.inside_method = prev_inside_method
            self.current_function = prev_function
        else:
            # This is an async function
            self.parser.functions.append(func_info)
            prev_function = self.current_function
            self.current_function = node.name
            # Visit nested functions
            self.nesting_level += 1
            self.generic_visit(node)
            self.nesting_level -= 1
            self.current_function = prev_function
    
    def visit_ClassDef(self, node):
        """Visit class definitions."""
        class_info = {
            'name': node.name,
            'line': node.lineno,
            'bases': [self._get_base_name(base) for base in node.bases],
            'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
            'methods': [],
            'class_variables': [],
            'instance_variables': [],
            'docstring': self._get_docstring(node.body)
        }
        
        # Check for decorators
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name not in [d['name'] for d in self.parser.decorators]:
                self.parser.decorators.append({
                    'name': decorator_name,
                    'line': decorator.lineno if hasattr(decorator, 'lineno') else None
                })
        
        # Store previous class context
        prev_class = self.current_class
        self.current_class = class_info
        
        # Visit class body to find methods and variables
        self.generic_visit(node)
        
        self.parser.classes.append(class_info)
        self.current_class = prev_class
    
    def visit_Assign(self, node):
        """Visit assignment statements to find variables."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                var_info = {
                    'name': var_name,
                    'line': node.lineno,
                    'type': self._infer_type(node.value) or 'unknown',
                    'source': None  # Will be set based on context
                }
                
                if self.current_class and not self.inside_method:
                    # Class variable (assigned at class level, not inside a method)
                    var_info['source'] = 'class_variable'
                    if var_name not in [v['name'] for v in self.current_class['class_variables']]:
                        self.current_class['class_variables'].append(var_info)
                elif not self.current_class and self.current_function is None and self.nesting_level == 0:
                    # Check if we're inside if __name__ == "__main__"
                    if self.inside_name_main:
                        # Execution-scope variable
                        exec_var_info = {
                            'name': var_name,
                            'line': node.lineno,
                            'type': self._infer_type(node.value) or 'unknown',
                            'source': 'execution_scope'
                        }
                        if var_name not in [v['name'] for v in self.parser.execution_scope_vars]:
                            self.parser.execution_scope_vars.append(exec_var_info)
                    else:
                        # Global variable - only at module level (not inside function or class or __main__)
                        var_info['source'] = 'global'
                        if var_name not in [v['name'] for v in self.parser.global_vars]:
                            self.parser.global_vars.append(var_info)
                elif self.current_function is not None:
                    # Local variable - inside a function or method
                    local_var_info = {
                        'name': var_name,
                        'line': node.lineno,
                        'type': self._infer_type(node.value) or 'unknown',
                        'source': 'local',
                        'function': self.current_function,
                        'is_method': self.inside_method
                    }
                    # Check if this variable is already tracked for this function
                    existing = [v for v in self.parser.local_vars 
                               if v['name'] == var_name and v['function'] == self.current_function]
                    if not existing:
                        self.parser.local_vars.append(local_var_info)
            elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                # Instance variable (self.attr = value)
                if target.value.id == 'self':
                    var_info = {
                        'name': target.attr,
                        'line': node.lineno,
                        'type': self._infer_type(node.value) if node.value else 'unknown',
                        'source': 'instance_variable'
                    }
                    if self.current_class:
                        if var_info['name'] not in [v['name'] for v in self.current_class['instance_variables']]:
                            self.current_class['instance_variables'].append(var_info)
        
        self.generic_visit(node)
    
    def visit_AnnAssign(self, node):
        """Visit annotated assignment statements."""
        if isinstance(node.target, ast.Name):
            var_name = node.target.id
            var_info = {
                'name': var_name,
                'line': node.lineno,
                'type': self._get_annotation_name(node.annotation) if node.annotation else 'unknown',
                'source': None  # Will be set based on context
            }
            
            if self.current_class and not self.inside_method:
                # Class variable (annotated at class level)
                var_info['source'] = 'class_variable'
                if var_name not in [v['name'] for v in self.current_class['class_variables']]:
                    self.current_class['class_variables'].append(var_info)
            elif not self.current_class and self.current_function is None and self.nesting_level == 0:
                # Check if we're inside if __name__ == "__main__"
                if self.inside_name_main:
                    # Execution-scope variable
                    exec_var_info = {
                        'name': var_name,
                        'line': node.lineno,
                        'type': self._get_annotation_name(node.annotation) if node.annotation else 'unknown',
                        'source': 'execution_scope'
                    }
                    if var_name not in [v['name'] for v in self.parser.execution_scope_vars]:
                        self.parser.execution_scope_vars.append(exec_var_info)
                else:
                    # Global variable - only at module level (not inside function or class or __main__)
                    var_info['source'] = 'global'
                    if var_name not in [v['name'] for v in self.parser.global_vars]:
                        self.parser.global_vars.append(var_info)
            elif self.current_function is not None:
                # Local variable - inside a function or method
                local_var_info = {
                    'name': var_name,
                    'line': node.lineno,
                    'type': self._get_annotation_name(node.annotation) if node.annotation else 'unknown',
                    'source': 'local',
                    'function': self.current_function,
                    'is_method': self.inside_method
                }
                # Check if this variable is already tracked for this function
                existing = [v for v in self.parser.local_vars 
                           if v['name'] == var_name and v['function'] == self.current_function]
                if not existing:
                    self.parser.local_vars.append(local_var_info)
        elif isinstance(node.target, ast.Attribute) and isinstance(node.target.value, ast.Name):
            if node.target.value.id == 'self':
                var_info = {
                    'name': node.target.attr,
                    'line': node.lineno,
                    'type': self._get_annotation_name(node.annotation) if node.annotation else 'unknown',
                    'source': 'instance_variable'
                }
                if self.current_class:
                    if var_info['name'] not in [v['name'] for v in self.current_class['instance_variables']]:
                        self.current_class['instance_variables'].append(var_info)
        
        self.generic_visit(node)
    
    def visit_Import(self, node):
        """Visit import statements."""
        for alias in node.names:
            import_info = {
                'module': alias.name,
                'alias': alias.asname,
                'line': node.lineno,
                'type': 'import'
            }
            self.parser.imports.append(import_info)
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Visit from ... import statements."""
        module = node.module if node.module else ''
        for alias in node.names:
            import_info = {
                'module': module,
                'name': alias.name,
                'alias': alias.asname,
                'line': node.lineno,
                'type': 'from_import'
            }
            self.parser.imports.append(import_info)
        
        self.generic_visit(node)
    
    def visit_Global(self, node):
        """Visit global declarations."""
        if self.current_function:
            if self.current_function not in self.parser.global_declarations:
                self.parser.global_declarations[self.current_function] = []
            # node.names is a list of strings, not AST nodes
            self.parser.global_declarations[self.current_function].extend(node.names)
        self.generic_visit(node)
    
    def visit_Nonlocal(self, node):
        """Visit nonlocal declarations."""
        if self.current_function:
            if self.current_function not in self.parser.nonlocal_declarations:
                self.parser.nonlocal_declarations[self.current_function] = []
            # node.names is a list of strings, not AST nodes
            self.parser.nonlocal_declarations[self.current_function].extend(node.names)
        self.generic_visit(node)
    
    def _get_decorator_name(self, node):
        """Extract decorator name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id
            elif isinstance(node.func, ast.Attribute):
                return self._get_attribute_name(node.func)
        return 'unknown'
    
    def _get_attribute_name(self, node):
        """Get full attribute name (e.g., 'module.function')."""
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._get_attribute_name(node.value)}.{node.attr}"
        return node.attr
    
    def _get_base_name(self, node):
        """Extract base class name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        return 'unknown'
    
    def _get_annotation_name(self, node):
        """Extract type annotation name."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        elif isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                return node.value.id
        return 'unknown'
    
    def _get_docstring(self, body):
        """Extract docstring from function/class body."""
        if not body:
            return None
        
        # First statement should be an Expr with a Constant string
        first_stmt = body[0]
        if isinstance(first_stmt, ast.Expr):
            if isinstance(first_stmt.value, ast.Constant) and isinstance(first_stmt.value.value, str):
                docstring = first_stmt.value.value.strip()
                # Get first line or first sentence
                lines = docstring.split('\n')
                first_line = lines[0].strip()
                # Limit to 80 characters for diagram display
                if len(first_line) > 80:
                    first_line = first_line[:77] + "..."
                return first_line
        return None
    
    def _get_return_annotation(self, node):
        """Extract return type annotation."""
        return self._get_annotation_name(node)
    
    def visit_Call(self, node):
        """Visit function/method calls to track relationships and control flow."""
        if not self.current_function:
            self.generic_visit(node)
            return
        
        caller = self.current_function
        line = node.lineno
        
        # Extract call information for control flow
        call_name = None
        call_label = None
        
        # Get the function being called
        if isinstance(node.func, ast.Name):
            # Direct function call: function_name()
            callee = node.func.id
            call_name = callee
            call_label = f"{callee}()"
            # Check if it's a class instantiation
            class_names = [cls['name'] for cls in self.parser.classes]
            if callee in class_names:
                self.parser.class_instantiations.append({
                    'caller': caller,
                    'class_name': callee,
                    'line': line
                })
            else:
                # Regular function call
                self.parser.function_calls.append({
                    'caller': caller,
                    'callee': callee,
                    'line': line
                })
                # Check if callee is from an import
                self._track_import_usage(callee, caller, line)
        elif isinstance(node.func, ast.Attribute):
            # Method call or attribute access: obj.method()
            if isinstance(node.func.value, ast.Name):
                obj_name = node.func.value.id
                method_name = node.func.attr
                call_name = f"{obj_name}.{method_name}"
                call_label = f"{obj_name}.{method_name}()"
                
                # Check if it's self.method() - method call within class
                if obj_name == 'self' and self.current_class:
                    # Internal method call
                    self.parser.method_calls.append({
                        'caller': caller,
                        'class_name': self.current_class['name'],
                        'method': method_name,
                        'line': line
                    })
                else:
                    # External method call or attribute access
                    full_name = f"{obj_name}.{method_name}"
                    self.parser.function_calls.append({
                        'caller': caller,
                        'callee': full_name,
                        'line': line
                    })
                    # Check if obj_name is from an import
                    self._track_import_usage(obj_name, caller, line)
            else:
                # Complex attribute access
                full_name = self._get_attribute_name(node.func)
                call_name = full_name
                call_label = f"{full_name}()"
                self.parser.function_calls.append({
                    'caller': caller,
                    'callee': full_name,
                    'line': line
                })
                # Try to extract module from complex attribute
                if isinstance(node.func.value, ast.Attribute):
                    module_part = self._extract_module_from_attribute(node.func.value)
                    if module_part:
                        self._track_import_usage(module_part, caller, line)
        
        # Add function call to control flow for flowchart generation
        if call_name and self.current_function:
            # Create a descriptive action label
            action_label = self._create_action_label(call_name, call_label)
            self.parser.control_flow.append({
                'type': 'call',
                'function': self.current_function,
                'line': line,
                'call_name': call_name,
                'call_label': call_label,
                'action_label': action_label
            })
        
        self.generic_visit(node)
    
    def _create_action_label(self, call_name: str, call_label: str) -> str:
        """Create a descriptive action label for a function call."""
        # Common patterns for action labels
        call_lower = call_name.lower()
        
        # Method calls with common patterns
        if '.listen' in call_lower or 'listen' in call_lower:
            return "Listen to microphone"
        elif '.recognize' in call_lower or 'recognize' in call_lower:
            return "Recognize speech"
        elif '.speak' in call_lower or 'speak' in call_lower:
            return "Speak"
        elif 'print' in call_lower:
            return "Print output"
        elif '.read' in call_lower or 'read' in call_lower:
            return "Read data"
        elif '.write' in call_lower or 'write' in call_lower:
            return "Write data"
        elif '.open' in call_lower or 'open' in call_lower:
            return "Open file"
        elif '.close' in call_lower or 'close' in call_lower:
            return "Close resource"
        elif '.get' in call_lower:
            return "Get data"
        elif '.set' in call_lower:
            return "Set value"
        elif '.send' in call_lower:
            return "Send data"
        elif '.receive' in call_lower:
            return "Receive data"
        else:
            # Default: use the call label but make it more readable
            return call_label.replace('()', '')
    
    def _track_import_usage(self, name: str, entity: str, line: int):
        """Track if a name is from an import."""
        # Check all imports to see if this name matches
        for imp in self.parser.imports:
            if imp['type'] == 'import':
                # import module -> check if name matches module or module.name
                module = imp['module']
                if name == module or name.startswith(module + '.'):
                    self.parser.import_usage.append({
                        'entity': entity,
                        'import_module': module,
                        'import_name': name,
                        'line': line
                    })
            elif imp['type'] == 'from_import':
                # from module import name -> check if name matches
                if imp.get('name') == name:
                    module = imp.get('module', '')
                    self.parser.import_usage.append({
                        'entity': entity,
                        'import_module': module,
                        'import_name': name,
                        'line': line
                    })
                # Also check if name matches module
                elif imp.get('module') and name.startswith(imp['module'] + '.'):
                    self.parser.import_usage.append({
                        'entity': entity,
                        'import_module': imp['module'],
                        'import_name': name,
                        'line': line
                    })
    
    def _extract_module_from_attribute(self, node):
        """Extract module name from attribute access like module.submodule.func."""
        if isinstance(node.value, ast.Name):
            return node.value.id
        elif isinstance(node.value, ast.Attribute):
            return self._extract_module_from_attribute(node.value)
        return None
    
    def visit_If(self, node):
        """Track if/else control flow."""
        # Check if this is "if __name__ == '__main__'"
        is_name_main = self._is_name_main_check(node.test)
        
        if is_name_main and not self.current_function:
            # We're entering the if __name__ == "__main__" block at module level
            prev_inside_name_main = self.inside_name_main
            self.inside_name_main = True
            self.generic_visit(node)
            self.inside_name_main = prev_inside_name_main
        else:
            # Regular if statement
            if self.current_function:
                flow_info = {
                    'type': 'if',
                    'function': self.current_function,
                    'line': node.lineno,
                    'condition': self._get_condition_string(node.test),
                    'has_else': len(node.orelse) > 0
                }
                self.parser.control_flow.append(flow_info)
            self.generic_visit(node)
    
    def _is_name_main_check(self, node):
        """Check if an AST node represents 'if __name__ == "__main__"'."""
        if isinstance(node, ast.Compare):
            if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                if isinstance(node.left, ast.Name) and node.left.id == '__name__':
                    if len(node.comparators) == 1:
                        comparator = node.comparators[0]
                        if isinstance(comparator, ast.Constant) and comparator.value == '__main__':
                            return True
                        elif isinstance(comparator, ast.Str) and comparator.s == '__main__':
                            return True
        return False
    
    def visit_For(self, node):
        """Track for loop control flow."""
        if self.current_function:
            flow_info = {
                'type': 'for',
                'function': self.current_function,
                'line': node.lineno,
                'target': self._get_target_string(node.target),
                'iter': self._get_iter_string(node.iter)
            }
            self.parser.control_flow.append(flow_info)
        self.generic_visit(node)
    
    def visit_While(self, node):
        """Track while loop control flow."""
        if self.current_function:
            flow_info = {
                'type': 'while',
                'function': self.current_function,
                'line': node.lineno,
                'condition': self._get_condition_string(node.test)
            }
            self.parser.control_flow.append(flow_info)
        self.generic_visit(node)
    
    def visit_Try(self, node):
        """Track try/except control flow with exception types."""
        if self.current_function:
            # Extract exception types from handlers
            exceptions = []
            for handler in node.handlers:
                if handler.type:
                    # Get exception type name
                    if isinstance(handler.type, ast.Name):
                        exceptions.append(handler.type.id)
                    elif isinstance(handler.type, ast.Attribute):
                        # Handle cases like sr.UnknownValueError
                        full_name = self._get_attribute_name(handler.type)
                        exceptions.append(full_name)
                    elif isinstance(handler.type, ast.Tuple):
                        # Multiple exception types: except (A, B, C)
                        for exc in handler.type.elts:
                            if isinstance(exc, ast.Name):
                                exceptions.append(exc.id)
                            elif isinstance(exc, ast.Attribute):
                                exceptions.append(self._get_attribute_name(exc))
                            else:
                                exceptions.append("Exception")
                    else:
                        exceptions.append("Exception")
                else:
                    # Bare except: except:
                    exceptions.append("Exception")
            
            flow_info = {
                'type': 'try',
                'function': self.current_function,
                'line': node.lineno,
                'has_except': len(node.handlers) > 0,
                'has_finally': len(node.finalbody) > 0,
                'exceptions': exceptions if exceptions else ['Exception']
            }
            self.parser.control_flow.append(flow_info)
        self.generic_visit(node)
    
    def visit_With(self, node):
        """Track with statement control flow with context manager names."""
        if self.current_function:
            # Extract context manager names and create descriptive labels
            items = []
            for item in node.items:
                context_expr = self._get_context_expr_string(item.context_expr)
                # If there's an optional variable, use it; otherwise use the context expression
                if item.optional_vars:
                    var_name = self._get_target_string(item.optional_vars)
                    items.append({
                        'var': var_name,
                        'context': context_expr,
                        'label': f"Enter {context_expr}" if context_expr else "Enter context"
                    })
                else:
                    items.append({
                        'var': None,
                        'context': context_expr,
                        'label': f"Enter {context_expr}" if context_expr else "Enter context"
                    })
            
            flow_info = {
                'type': 'with',
                'function': self.current_function,
                'line': node.lineno,
                'items': items
            }
            self.parser.control_flow.append(flow_info)
        self.generic_visit(node)
    
    def visit_Return(self, node):
        """Track return statements."""
        if self.current_function:
            flow_info = {
                'type': 'return',
                'function': self.current_function,
                'line': node.lineno,
                'has_value': node.value is not None
            }
            self.parser.control_flow.append(flow_info)
        self.generic_visit(node)
    
    def visit_Break(self, node):
        """Track break statements."""
        if self.current_function:
            flow_info = {
                'type': 'break',
                'function': self.current_function,
                'line': node.lineno
            }
            self.parser.control_flow.append(flow_info)
        self.generic_visit(node)
    
    def visit_Continue(self, node):
        """Track continue statements."""
        if self.current_function:
            flow_info = {
                'type': 'continue',
                'function': self.current_function,
                'line': node.lineno
            }
            self.parser.control_flow.append(flow_info)
        self.generic_visit(node)
    
    def _get_condition_string(self, node):
        """Get string representation of a condition."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Compare):
            left = self._get_condition_string(node.left)
            ops = [self._get_op_string(op) for op in node.ops]
            comparators = [self._get_condition_string(comp) for comp in node.comparators]
            return f"{left} {ops[0]} {comparators[0]}" if len(ops) == 1 else f"{left} {ops[0]} {comparators[0]} ..."
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return f"{node.func.id}()"
            elif isinstance(node.func, ast.Attribute):
                return f"{self._get_attribute_name(node.func)}()"
        return "condition"
    
    def _get_op_string(self, op):
        """Get string representation of comparison operator."""
        op_map = {
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
            ast.Is: "is",
            ast.IsNot: "is not",
            ast.In: "in",
            ast.NotIn: "not in"
        }
        return op_map.get(type(op), "?")
    
    def _get_target_string(self, node):
        """Get string representation of a target."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Tuple):
            return f"({', '.join([self._get_target_string(el) for el in node.elts])})"
        return "target"
    
    def _get_iter_string(self, node):
        """Get string representation of an iterable."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return f"{node.func.id}()"
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        return "iterable"
    
    def _get_with_item_string(self, item):
        """Get string representation of a with item."""
        if item.optional_vars:
            return f"{self._get_target_string(item.optional_vars)} = {self._get_context_expr_string(item.context_expr)}"
        return self._get_context_expr_string(item.context_expr)
    
    def _get_context_expr_string(self, node):
        """Get string representation of a context expression."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id
            elif isinstance(node.func, ast.Attribute):
                # Handle cases like Microphone() or r.listen()
                if isinstance(node.func.value, ast.Name):
                    return node.func.value.id
                return self._get_attribute_name(node.func)
        elif isinstance(node, ast.Attribute):
            # Handle attribute access like sr.Microphone
            return self._get_attribute_name(node)
        return "context"
    
    def _infer_type(self, node):
        """Infer type from AST node value."""
        if isinstance(node, ast.Constant):
            return type(node.value).__name__
        elif isinstance(node, ast.List):
            return 'list'
        elif isinstance(node, ast.Dict):
            return 'dict'
        elif isinstance(node, ast.Tuple):
            return 'tuple'
        elif isinstance(node, ast.Set):
            return 'set'
        elif isinstance(node, ast.NameConstant):
            return 'bool' if isinstance(node.value, bool) else 'NoneType'
        return 'unknown'

