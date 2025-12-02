import ast
from typing import Dict, List, Any
from collections import defaultdict

class CodeParser:
    def __init__(self):
        self.functions = []
        self.classes = []
        self.global_vars = []
        self.imports = []
        self.decorators = []
        self.function_calls = []  # Track function calls: (caller, callee, line)
        self.method_calls = []  # Track method calls: (caller_class, method, line)
        self.class_instantiations = []  # Track class instantiations: (caller, class_name, line)
        self.control_flow = []  # Track control flow structures for flowcharts
        
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
        self.imports = []
        self.decorators = []
        self.function_calls = []
        self.method_calls = []
        self.class_instantiations = []
        self.control_flow = []
        
        # Visit all nodes
        visitor = CodeVisitor(self)
        visitor.visit(tree)
        
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
                'class_variables': len(class_vars),
                'instance_variables': len(instance_vars),
                'total_decorators': len(self.decorators),
                'total_imports': len(self.imports)
            },
            'functions': self.functions,
            'classes': self.classes,
            'global_variables': self.global_vars,
            'imports': self.imports,
            'decorators': self.decorators,
            'function_calls': self.function_calls,
            'method_calls': self.method_calls,
            'class_instantiations': self.class_instantiations,
            'control_flow': self.control_flow
        }


class CodeVisitor(ast.NodeVisitor):
    def __init__(self, parser: CodeParser):
        self.parser = parser
        self.current_class = None
        self.current_function = None
        self.nesting_level = 0
        self.inside_method = False
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
            'returns': self._get_return_annotation(node.returns) if node.returns else None
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
            'returns': self._get_return_annotation(node.returns) if node.returns else None
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
            'instance_variables': []
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
                    'type': self._infer_type(node.value)
                }
                
                if self.current_class and not self.inside_method:
                    # Class variable (assigned at class level, not inside a method)
                    if var_name not in [v['name'] for v in self.current_class['class_variables']]:
                        self.current_class['class_variables'].append(var_info)
                elif not self.current_class:
                    # Global variable
                    if var_name not in [v['name'] for v in self.parser.global_vars]:
                        self.parser.global_vars.append(var_info)
            elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                # Instance variable (self.attr = value)
                if target.value.id == 'self':
                    var_info = {
                        'name': target.attr,
                        'line': node.lineno,
                        'type': self._infer_type(node.value) if node.value else None
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
                'type': self._get_annotation_name(node.annotation) if node.annotation else None
            }
            
            if self.current_class and not self.inside_method:
                # Class variable (annotated at class level)
                if var_name not in [v['name'] for v in self.current_class['class_variables']]:
                    self.current_class['class_variables'].append(var_info)
            elif not self.current_class:
                # Global variable
                if var_name not in [v['name'] for v in self.parser.global_vars]:
                    self.parser.global_vars.append(var_info)
        elif isinstance(node.target, ast.Attribute) and isinstance(node.target.value, ast.Name):
            if node.target.value.id == 'self':
                var_info = {
                    'name': node.target.attr,
                    'line': node.lineno,
                    'type': self._get_annotation_name(node.annotation) if node.annotation else None
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
    
    def _get_return_annotation(self, node):
        """Extract return type annotation."""
        return self._get_annotation_name(node)
    
    def visit_Call(self, node):
        """Visit function/method calls to track relationships."""
        if not self.current_function:
            self.generic_visit(node)
            return
        
        caller = self.current_function
        line = node.lineno
        
        # Get the function being called
        if isinstance(node.func, ast.Name):
            # Direct function call: function_name()
            callee = node.func.id
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
        elif isinstance(node.func, ast.Attribute):
            # Method call or attribute access: obj.method()
            if isinstance(node.func.value, ast.Name):
                obj_name = node.func.value.id
                method_name = node.func.attr
                
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
            else:
                # Complex attribute access
                full_name = self._get_attribute_name(node.func)
                self.parser.function_calls.append({
                    'caller': caller,
                    'callee': full_name,
                    'line': line
                })
        
        self.generic_visit(node)
    
    def visit_If(self, node):
        """Track if/else control flow."""
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
        """Track try/except control flow."""
        if self.current_function:
            flow_info = {
                'type': 'try',
                'function': self.current_function,
                'line': node.lineno,
                'has_except': len(node.handlers) > 0,
                'has_finally': len(node.finalbody) > 0
            }
            self.parser.control_flow.append(flow_info)
        self.generic_visit(node)
    
    def visit_With(self, node):
        """Track with statement control flow."""
        if self.current_function:
            flow_info = {
                'type': 'with',
                'function': self.current_function,
                'line': node.lineno,
                'items': [self._get_with_item_string(item) for item in node.items]
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
                return f"{node.func.id}()"
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

