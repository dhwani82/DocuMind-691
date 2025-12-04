"""Generate Mermaid diagrams from parsed code relationships."""
from typing import Dict, List, Any, Set, Tuple


class DiagramGenerator:
    """Generate Mermaid diagrams based on parsed code relationships."""
    
    def __init__(self, parse_result: Dict[str, Any]):
        """Initialize with parse results.
        
        Args:
            parse_result: Result from CodeParser.parse()
        """
        self.parse_result = parse_result
        self.classes = parse_result.get('classes', [])
        self.functions = parse_result.get('functions', [])
        self.function_calls = parse_result.get('function_calls', [])
        self.method_calls = parse_result.get('method_calls', [])
        self.class_instantiations = parse_result.get('class_instantiations', [])
        self.imports = parse_result.get('imports', [])
        self.control_flow = parse_result.get('control_flow', [])
        self.import_usage = parse_result.get('import_usage', [])
    
    def generate_architecture_diagram(self) -> str:
        """Generate Mermaid diagram showing comprehensive code structure.
        
        Shows categorized sections: Components, Services, Models, Helpers, Entry Points.
        Each class includes its docstring or inferred role as a subtitle.
        For SQL: shows database schema with tables and foreign key relationships.
        
        Returns:
            Mermaid diagram code as string
        """
        language = self.parse_result.get('language', 'python').lower()
        
        # Handle SQL language - show database schema
        if language == 'sql':
            return self._generate_sql_architecture_diagram()
        
        lines = ["```mermaid", "graph TD"]
        lines.append("    direction TB")
        
        # Root node - the module/file
        root_id = "MODULE"
        lines.append(f"    {root_id}[\"📄 Module\"]")
        lines.append(f"    style {root_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        
        # Categorize classes and functions
        categorized = self._categorize_code_elements()
        
        # Add imports section
        self._add_imports_section(lines, root_id)
        
        # Add categorized sections
        self._add_categorized_sections(lines, root_id, categorized)
        
        # Add execution entry point
        self._add_execution_entry_point(lines, root_id)
        
        # Add global variables
        self._add_global_variables(lines, root_id)
        
        lines.append("```")
        return "\n".join(lines)
    
    def _categorize_code_elements(self) -> Dict[str, Dict[str, List[Any]]]:
        """Categorize classes and functions into Components, Services, Models, Helpers, Entry Points.
        
        Returns:
            Dictionary with categories as keys, each containing 'classes' and 'functions' lists
        """
        categorized = {
            'components': {'classes': [], 'functions': []},
            'services': {'classes': [], 'functions': []},
            'models': {'classes': [], 'functions': []},
            'helpers': {'classes': [], 'functions': []},
            'entry_points': {'classes': [], 'functions': []}
        }
        
        # Categorize classes
        for cls in self.classes:
            category = self._categorize_class(cls)
            categorized[category]['classes'].append(cls)
        
        # Categorize top-level functions
        top_level_funcs = [f for f in self.functions if not f.get('is_nested', False)]
        for func in top_level_funcs:
            category = self._categorize_function(func)
            categorized[category]['functions'].append(func)
        
        return categorized
    
    def _categorize_class(self, cls: Dict[str, Any]) -> str:
        """Determine category for a class based on name, docstring, and patterns.
        
        Returns:
            Category name: 'components', 'services', 'models', 'helpers', or 'entry_points'
        """
        name_lower = cls['name'].lower()
        docstring = cls.get('docstring', '').lower() if cls.get('docstring') else ''
        combined = f"{name_lower} {docstring}"
        
        # Entry Points: Main, App, Application, Server, Runner (check name first for priority)
        entry_point_keywords = ['main', 'app', 'application', 'server', 'runner', 'entry', 'start', 'launch']
        if any(kw in name_lower for kw in entry_point_keywords):
            return 'entry_points'
        
        # Services: Service, Manager, Handler, Controller, API, Client (check name first)
        service_keywords = ['service', 'manager', 'handler', 'controller', 'api', 'client', 'processor', 'executor']
        if any(kw in name_lower for kw in service_keywords):
            return 'services'
        # Also check in combined for docstring mentions
        if any(kw in docstring for kw in service_keywords):
            return 'services'
        
        # Components: Component, Widget, View, UI, Panel, Frame (check name first)
        component_keywords = ['component', 'widget', 'view', 'ui', 'panel', 'frame', 'window', 'dialog']
        if any(kw in name_lower for kw in component_keywords):
            return 'components'
        if any(kw in docstring for kw in component_keywords):
            return 'components'
        
        # Models: Model, Entity, Data, Schema, Record, DTO (check name first)
        model_keywords = ['model', 'entity', 'schema', 'record', 'dto', 'dataclass', 'table']
        if any(kw in name_lower for kw in model_keywords):
            return 'models'
        # "data" is too generic, only check if it's in name, not docstring
        if 'data' in name_lower and 'model' in name_lower:
            return 'models'
        if any(kw in docstring for kw in ['model', 'entity', 'schema', 'record']):
            return 'models'
        
        # Default to components if it has methods (likely a component)
        if cls.get('methods'):
            return 'components'
        
        # Default to models if it has class variables (likely a data model)
        if cls.get('class_variables') or cls.get('instance_variables'):
            return 'models'
        
        # Default fallback
        return 'components'
    
    def _categorize_function(self, func: Dict[str, Any]) -> str:
        """Determine category for a function based on name, docstring, and patterns.
        
        Returns:
            Category name: 'components', 'services', 'models', 'helpers', or 'entry_points'
        """
        name_lower = func['name'].lower()
        docstring = func.get('docstring', '').lower() if func.get('docstring') else ''
        combined = f"{name_lower} {docstring}"
        
        # Entry Points: main, run, start, launch, execute (check name first)
        entry_point_keywords = ['main', 'run', 'start', 'launch', 'execute', 'entry']
        if any(kw in name_lower for kw in entry_point_keywords):
            return 'entry_points'
        
        # Components: render, display, show, draw, paint (check name first)
        component_keywords = ['render', 'display', 'show', 'draw', 'paint']
        if any(kw in name_lower for kw in component_keywords):
            return 'components'
        if any(kw in docstring for kw in ['render', 'display', 'ui', 'view']):
            return 'components'
        
        # Services: process, handle, manage, serve, api (check name first)
        service_keywords = ['process', 'handle', 'manage', 'serve', 'api', 'request', 'response']
        if any(kw in name_lower for kw in service_keywords):
            return 'services'
        if any(kw in docstring for kw in service_keywords):
            return 'services'
        
        # Models: create, build, parse, serialize (check name first, but be careful)
        # Only categorize as model if it's clearly model-related
        model_keywords = ['to_dict', 'from_dict', 'serialize', 'deserialize']
        if any(kw in name_lower for kw in model_keywords):
            return 'models'
        if any(kw in docstring for kw in ['model', 'entity', 'serialize']):
            return 'models'
        
        # Helper keywords: format, validate, convert, transform, utility, helper
        helper_keywords = ['format', 'validate', 'convert', 'transform', 'utility', 'helper', 'parse']
        if any(kw in name_lower for kw in helper_keywords):
            return 'helpers'
        if any(kw in docstring for kw in ['helper', 'utility', 'format', 'validate']):
            return 'helpers'
        
        # Default to helpers (utility functions)
        return 'helpers'
    
    def _get_class_role(self, cls: Dict[str, Any]) -> str:
        """Get class role from docstring or infer from name/patterns.
        
        Returns:
            Short description of class role (max 60 chars)
        """
        # Try docstring first
        if cls.get('docstring'):
            docstring = cls['docstring'].strip()
            # Get first sentence or first line
            first_line = docstring.split('.')[0].split('\n')[0].strip()
            if len(first_line) > 60:
                first_line = first_line[:57] + "..."
            if first_line:
                return first_line
        
        # Infer from name and patterns
        name = cls['name']
        name_lower = name.lower()
        
        # Common patterns
        if 'model' in name_lower or 'entity' in name_lower:
            return "Data model representing structured information"
        elif 'service' in name_lower or 'manager' in name_lower:
            return "Service layer for business logic"
        elif 'controller' in name_lower or 'handler' in name_lower:
            return "Controller handling requests and responses"
        elif 'component' in name_lower or 'widget' in name_lower:
            return "UI component for user interaction"
        elif 'client' in name_lower or 'api' in name_lower:
            return "API client for external communication"
        elif 'view' in name_lower:
            return "View component for displaying data"
        elif 'factory' in name_lower:
            return "Factory for creating instances"
        elif 'base' in name_lower or 'abstract' in name_lower:
            return "Base class providing common functionality"
        else:
            # Generic description based on methods
            method_count = len(cls.get('methods', []))
            if method_count > 0:
                return f"Class with {method_count} method{'s' if method_count > 1 else ''}"
            return "Class definition"
    
    def _add_imports_section(self, lines: List[str], root_id: str):
        """Add imports section to diagram."""
        import_modules = set()
        for imp in self.imports:
            if imp['type'] == 'import':
                module = imp['module'].split('.')[0]
                import_modules.add(module)
            elif imp['type'] == 'from_import' and imp['module']:
                module = imp['module'].split('.')[0]
                import_modules.add(module)
        
        if import_modules:
            imports_id = "IMPORTS"
            lines.append(f"    {root_id} --> {imports_id}[\"📚 Imports ({len(import_modules)})\"]")
            lines.append(f"    style {imports_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
            
            for module in sorted(list(import_modules))[:6]:
                module_id = f"IMP_{module}".replace('.', '_').replace('-', '_')
                lines.append(f"    {imports_id} --> {module_id}[\"📦 {module}\"]")
                lines.append(f"    style {module_id} fill:#ffe0b2,stroke:#f57c00")
            
            if len(import_modules) > 6:
                more_imports_id = "MORE_IMPORTS"
                lines.append(f"    {imports_id} --> {more_imports_id}[\"... {len(import_modules) - 6} more\"]")
                lines.append(f"    style {more_imports_id} fill:#f5f5f5,stroke:#999")
    
    def _add_categorized_sections(self, lines: List[str], root_id: str, categorized: Dict[str, Dict[str, List[Any]]]):
        """Add categorized sections (Components, Services, Models, Helpers, Entry Points) to diagram."""
        section_configs = [
            ('components', '🏗️ Components', '#e1f5fe', '#0288d1', '#b3e5fc', '#0277bd'),
            ('services', '⚙️ Services', '#f3e5f5', '#9c27b0', '#e1bee7', '#7b1fa2'),
            ('models', '📊 Models', '#fff3e0', '#f57c00', '#ffe0b2', '#e65100'),
            ('helpers', '🛠️ Helpers', '#e8f5e9', '#388e3c', '#c8e6c9', '#2e7d32'),
            ('entry_points', '🚀 Entry Points', '#fce4ec', '#c2185b', '#f8bbd0', '#880e4f')
        ]
        
        for section_key, section_label, section_fill, section_stroke, item_fill, item_stroke in section_configs:
            section_data = categorized[section_key]
            classes = section_data['classes']
            functions = section_data['functions']
            
            if not classes and not functions:
                continue
            
            total_count = len(classes) + len(functions)
            section_id = section_key.upper().replace('_', '_')
            lines.append(f"    {root_id} --> {section_id}[\"{section_label} ({total_count})\"]")
            lines.append(f"    style {section_id} fill:{section_fill},stroke:{section_stroke},stroke-width:2px")
            
            # Add classes
            for cls in classes[:8]:
                class_id = f"{section_key.upper()}_CLASS_{cls['name']}".replace(' ', '_')
                class_label = cls['name']
                
                # Add base classes if any
                if cls.get('bases'):
                    bases_str = ', '.join(cls['bases'][:2])
                    if len(cls['bases']) > 2:
                        bases_str += f", +{len(cls['bases']) - 2}"
                    class_label = f"{class_label}({bases_str})"
                
                # Add role/subtitle from docstring
                role = self._get_class_role(cls)
                class_label += f"\\n<i>{role}</i>"
                
                lines.append(f"    {section_id} --> {class_id}[\"{class_label}\"]")
                lines.append(f"    style {class_id} fill:{item_fill},stroke:{item_stroke}")
                
                # Add inheritance relationships
                if cls.get('bases'):
                    for base in cls['bases']:
                        base_name = base.split('.')[-1]
                        # Find base class in categorized data
                        base_class = None
                        for cat_data in categorized.values():
                            for c in cat_data['classes']:
                                if c['name'] == base_name:
                                    base_class = c
                                    break
                            if base_class:
                                break
                        
                        if base_class:
                            # Find which section the base is in
                            base_section = None
                            for sec_key, sec_data in categorized.items():
                                if base_class in sec_data['classes']:
                                    base_section = sec_key
                                    break
                            
                            if base_section:
                                base_id = f"{base_section.upper()}_CLASS_{base_name}".replace(' ', '_')
                                lines.append(f"    {base_id} -.->|inherits| {class_id}")
            
            # Add functions
            for func in functions[:6]:
                func_id = f"{section_key.upper()}_FUNC_{func['name']}".replace(' ', '_')
                func_label = func['name']
                if func.get('is_async'):
                    func_label = f"🔁 {func_label}"
                func_label += "()"
                
                # Add docstring if available
                if func.get('docstring'):
                    docstring = func['docstring'].strip()
                    if len(docstring) > 50:
                        docstring = docstring[:47] + "..."
                    func_label += f"\\n<i>{docstring}</i>"
                
                lines.append(f"    {section_id} --> {func_id}[\"{func_label}\"]")
                lines.append(f"    style {func_id} fill:{item_fill},stroke:{item_stroke}")
            
            # Add "more" indicator if needed
            remaining = (len(classes) - 8) + (len(functions) - 6)
            if remaining > 0:
                more_id = f"MORE_{section_key.upper()}"
                lines.append(f"    {section_id} --> {more_id}[\"... {remaining} more\"]")
                lines.append(f"    style {more_id} fill:#f5f5f5,stroke:#999")
    
    def _add_execution_entry_point(self, lines: List[str], root_id: str):
        """Add execution entry point section."""
        execution_scope_vars = self.parse_result.get('execution_scope_variables', [])
        if execution_scope_vars:
            exec_id = "EXECUTION"
            lines.append(f"    {root_id} --> {exec_id}[\"▶️ Execution Scope\"]")
            lines.append(f"    style {exec_id} fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px")
            lines.append(f"    {exec_id} --> EXEC_VARS[\"Variables: {len(execution_scope_vars)}\"]")
            lines.append(f"    style EXEC_VARS fill:#e1bee7,stroke:#7b1fa2")
    
    def _add_global_variables(self, lines: List[str], root_id: str):
        """Add global variables section."""
        global_vars = self.parse_result.get('global_variables', [])
        if global_vars:
            globals_id = "GLOBALS"
            lines.append(f"    {root_id} --> {globals_id}[\"🌍 Global Variables ({len(global_vars)})\"]")
            lines.append(f"    style {globals_id} fill:#e0f2f1,stroke:#009688")
            
            for var in global_vars[:4]:
                var_id = f"GLOBAL_{var['name']}".replace(' ', '_')
                lines.append(f"    {globals_id} --> {var_id}[\"{var['name']}\"]")
                lines.append(f"    style {var_id} fill:#b2dfdb,stroke:#00796b")
    
    def _generate_functional_architecture(self, lines: List[str], root_id: str) -> str:
        """Generate architecture diagram for code without classes."""
        # Group imports by module
        import_modules = set()
        import_details = []
        for imp in self.imports:
            if imp['type'] == 'import':
                module = imp['module'].split('.')[0]
                import_modules.add(module)
                import_details.append({'module': module, 'name': None, 'type': 'import'})
            elif imp['type'] == 'from_import' and imp['module']:
                module = imp['module'].split('.')[0]
                import_modules.add(module)
                import_details.append({'module': module, 'name': imp.get('name'), 'type': 'from_import'})
        
        # Add imports section
        if import_modules:
            imports_id = "IMPORTS"
            lines.append(f"    {root_id} --> {imports_id}[\"📚 Imports ({len(import_modules)})\"]")
            lines.append(f"    style {imports_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
            
            # Show top imports
            for module in sorted(list(import_modules))[:8]:
                module_id = f"IMP_{module}".replace('.', '_').replace('-', '_')
                lines.append(f"    {imports_id} --> {module_id}[\"📦 {module}\"]")
                lines.append(f"    style {module_id} fill:#ffe0b2,stroke:#f57c00")
            
            if len(import_modules) > 8:
                more_imports_id = "MORE_IMPORTS"
                lines.append(f"    {imports_id} --> {more_imports_id}[\"... {len(import_modules) - 8} more\"]")
                lines.append(f"    style {more_imports_id} fill:#f5f5f5,stroke:#999")
        
        # Add top-level functions
        top_level_funcs = [f for f in self.functions if not f.get('is_nested', False)]
        if top_level_funcs:
            funcs_id = "FUNCTIONS"
            lines.append(f"    {root_id} --> {funcs_id}[\"⚙️ Functions ({len(top_level_funcs)})\"]")
            lines.append(f"    style {funcs_id} fill:#e3f2fd,stroke:#2196F3,stroke-width:2px")
            
            # Show functions
            for func in top_level_funcs[:10]:
                func_id = f"FUNC_{func['name']}".replace(' ', '_')
                func_label = func['name']
                if func.get('is_async'):
                    func_label = f"🔁 {func_label}"
                func_label += "()"
                
                # Add parameter count
                params = func.get('parameters', [])
                param_count = len([p for p in params if p != 'self'])
                if param_count > 0:
                    func_label += f"\\n({param_count} params)"
                
                lines.append(f"    {funcs_id} --> {func_id}[\"{func_label}\"]")
                lines.append(f"    style {func_id} fill:#bbdefb,stroke:#1976d2")
            
            if len(top_level_funcs) > 10:
                more_funcs_id = "MORE_FUNCS"
                lines.append(f"    {funcs_id} --> {more_funcs_id}[\"... {len(top_level_funcs) - 10} more\"]")
                lines.append(f"    style {more_funcs_id} fill:#f5f5f5,stroke:#999")
        
        # Add execution entry point (if __name__ == "__main__")
        execution_scope_vars = self.parse_result.get('execution_scope_variables', [])
        if execution_scope_vars:
            exec_id = "EXECUTION"
            lines.append(f"    {root_id} --> {exec_id}[\"▶️ Execution Entry Point\"]")
            lines.append(f"    style {exec_id} fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px")
            lines.append(f"    {exec_id} --> EXEC_VARS[\"Variables: {len(execution_scope_vars)}\"]")
            lines.append(f"    style EXEC_VARS fill:#e1bee7,stroke:#7b1fa2")
        
        # Add global variables if any
        global_vars = self.parse_result.get('global_variables', [])
        if global_vars:
            globals_id = "GLOBALS"
            lines.append(f"    {root_id} --> {globals_id}[\"🌍 Global Variables ({len(global_vars)})\"]")
            lines.append(f"    style {globals_id} fill:#e0f2f1,stroke:#009688")
            
            for var in global_vars[:5]:
                var_id = f"GLOBAL_{var['name']}".replace(' ', '_')
                lines.append(f"    {globals_id} --> {var_id}[\"{var['name']}\"]")
                lines.append(f"    style {var_id} fill:#b2dfdb,stroke:#00796b")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_class_based_architecture(self, lines: List[str], root_id: str) -> str:
        """Generate architecture diagram for code with classes, including context."""
        # Use graph TD to show comprehensive structure with classes
        lines = ["```mermaid", "graph TD"]
        lines.append("    direction TB")
        
        # Re-add root node
        lines.append(f"    {root_id}[\"📄 Module\"]")
        lines.append(f"    style {root_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        
        # Add imports section
        import_modules = set()
        for imp in self.imports:
            if imp['type'] == 'import':
                module = imp['module'].split('.')[0]
                import_modules.add(module)
            elif imp['type'] == 'from_import' and imp['module']:
                module = imp['module'].split('.')[0]
                import_modules.add(module)
        
        if import_modules:
            imports_id = "IMPORTS"
            lines.append(f"    {root_id} --> {imports_id}[\"📚 Imports ({len(import_modules)})\"]")
            lines.append(f"    style {imports_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
            
            for module in sorted(list(import_modules))[:5]:
                module_id = f"IMP_{module}".replace('.', '_').replace('-', '_')
                lines.append(f"    {imports_id} --> {module_id}[\"📦 {module}\"]")
                lines.append(f"    style {module_id} fill:#ffe0b2,stroke:#f57c00")
        
        # Add classes section (prominent)
        classes_id = "CLASSES"
        lines.append(f"    {root_id} --> {classes_id}[\"🏛️ Classes ({len(self.classes)})\"]")
        lines.append(f"    style {classes_id} fill:#e1f5fe,stroke:#0288d1,stroke-width:3px")
        
        for cls in self.classes:
            class_name = cls['name']
            class_id = f"CLASS_{class_name}".replace(' ', '_')
            
            # Format class label with base classes
            class_label = class_name
            if cls.get('bases'):
                bases_str = ', '.join(cls['bases'][:2])
                if len(cls['bases']) > 2:
                    bases_str += f", +{len(cls['bases']) - 2}"
                class_label = f"{class_name}({bases_str})"
            
            # Add method count
            method_count = len(cls.get('methods', []))
            if method_count > 0:
                class_label += f"\\n{method_count} method{'s' if method_count > 1 else ''}"
            
            lines.append(f"    {classes_id} --> {class_id}[\"{class_label}\"]")
            lines.append(f"    style {class_id} fill:#b3e5fc,stroke:#0277bd")
            
            # Add inheritance relationships
            if cls.get('bases'):
                for base in cls['bases']:
                    base_name = base.split('.')[-1]
                    if any(c['name'] == base_name for c in self.classes):
                        base_id = f"CLASS_{base_name}".replace(' ', '_')
                        lines.append(f"    {base_id} -.->|inherits| {class_id}")
        
        # Add top-level functions (non-nested)
        top_level_funcs = [f for f in self.functions if not f.get('is_nested', False)]
        if top_level_funcs:
            funcs_id = "FUNCTIONS"
            lines.append(f"    {root_id} --> {funcs_id}[\"⚙️ Functions ({len(top_level_funcs)})\"]")
            lines.append(f"    style {funcs_id} fill:#e3f2fd,stroke:#2196F3,stroke-width:2px")
            
            for func in top_level_funcs[:8]:
                func_id = f"FUNC_{func['name']}".replace(' ', '_')
                func_label = func['name']
                if func.get('is_async'):
                    func_label = f"🔁 {func_label}"
                func_label += "()"
                lines.append(f"    {funcs_id} --> {func_id}[\"{func_label}\"]")
                lines.append(f"    style {func_id} fill:#bbdefb,stroke:#1976d2")
        
        # Add execution entry point
        execution_scope_vars = self.parse_result.get('execution_scope_variables', [])
        if execution_scope_vars:
            exec_id = "EXECUTION"
            lines.append(f"    {root_id} --> {exec_id}[\"▶️ Execution Entry Point\"]")
            lines.append(f"    style {exec_id} fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px")
            lines.append(f"    {exec_id} --> EXEC_VARS[\"Variables: {len(execution_scope_vars)}\"]")
            lines.append(f"    style EXEC_VARS fill:#e1bee7,stroke:#7b1fa2")
        
        # Add global variables
        global_vars = self.parse_result.get('global_variables', [])
        if global_vars:
            globals_id = "GLOBALS"
            lines.append(f"    {root_id} --> {globals_id}[\"🌍 Global Variables ({len(global_vars)})\"]")
            lines.append(f"    style {globals_id} fill:#e0f2f1,stroke:#009688")
            
            for var in global_vars[:4]:
                var_id = f"GLOBAL_{var['name']}".replace(' ', '_')
                lines.append(f"    {globals_id} --> {var_id}[\"{var['name']}\"]")
                lines.append(f"    style {var_id} fill:#b2dfdb,stroke:#00796b")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_sql_architecture_diagram(self) -> str:
        """Generate architecture diagram for SQL showing database schema with tables and relationships."""
        tables = self.parse_result.get('tables', [])
        relationships = self.parse_result.get('relationships', [])
        
        if not tables:
            return "```mermaid\ngraph TD\n    A[\"📦 No Tables Found\"]\n    A --> B[\"Add CREATE TABLE statements to your SQL\"]\n    style A fill:#e8f4f8\n    style B fill:#fff4e6\n```"
        
        lines = ["```mermaid", "graph TD"]
        lines.append("    direction TB")
        
        # Root node
        root_id = "DATABASE"
        lines.append(f"    {root_id}[\"🗄️ Database Schema\"]")
        lines.append(f"    style {root_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        
        # Create table nodes with columns
        table_nodes = {}
        for table in tables:
            table_name = table['name']
            table_id = f"T_{table_name}".replace(' ', '_').replace('-', '_')
            table_nodes[table_name] = table_id
            
            columns = table.get('columns', [])
            
            # Build table label with key columns
            table_label = f"📊 {table_name}"
            if columns:
                # Show primary key columns first
                pk_cols = [c['name'] for c in columns if c.get('is_primary_key')]
                fk_cols = [c['name'] for c in columns if c.get('is_foreign_key')]
                
                if pk_cols:
                    table_label += f"\\n🔑 PK: {', '.join(pk_cols[:3])}"
                if fk_cols:
                    table_label += f"\\n🔗 FK: {', '.join(fk_cols[:3])}"
                table_label += f"\\n({len(columns)} columns)"
            
            lines.append(f"    {root_id} --> {table_id}[\"{table_label}\"]")
            lines.append(f"    style {table_id} fill:#e3f2fd,stroke:#2196F3,stroke-width:2px")
        
        # Add foreign key relationships
        for rel in relationships:
            from_table = rel.get('from_table')
            to_table = rel.get('to_table')
            from_column = rel.get('from_column')
            to_column = rel.get('to_column')
            
            if from_table in table_nodes and to_table in table_nodes:
                from_id = table_nodes[from_table]
                to_id = table_nodes[to_table]
                
                rel_label = f"{from_column} → {to_column}" if from_column and to_column else "FK"
                lines.append(f"    {from_id} -->|\"{rel_label}\"| {to_id}")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_sql_sequence_diagram(self) -> str:
        """Generate sequence diagram for SQL showing data flow through foreign key relationships."""
        tables = self.parse_result.get('tables', [])
        relationships = self.parse_result.get('relationships', [])
        
        if not tables:
            return "```mermaid\nsequenceDiagram\n    participant User as \"👤 User\"\n    User->>User: \"No tables found\"\n    Note over User: Add CREATE TABLE statements to see data flow\n```"
        
        if not relationships:
            return "```mermaid\nsequenceDiagram\n    participant User as \"👤 User\"\n    participant DB as \"🗄️ Database\"\n    User->>DB: \"Tables exist\"\n    DB-->>User: \"No foreign key relationships\"\n    Note over User,DB: Add FOREIGN KEY constraints to see data flow\n```"
        
        lines = ["```mermaid", "sequenceDiagram"]
        lines.append("    autonumber")
        lines.append("    participant User as \"👤 User/Application\"")
        
        # Add tables as participants
        table_participants = {}
        for table in tables:
            table_name = table['name']
            table_id = table_name.replace(' ', '_')
            table_participants[table_name] = table_id
            lines.append(f"    participant {table_id} as \"📊 {table_name}\"")
        
        # Show data flow through relationships
        lines.append("    User->>User: \"Database Operations\"")
        
        # Group relationships by from_table to show flow
        rels_by_table = {}
        for rel in relationships:
            from_table = rel.get('from_table')
            if from_table:
                if from_table not in rels_by_table:
                    rels_by_table[from_table] = []
                rels_by_table[from_table].append(rel)
        
        # Show relationships as data flow
        step = 1
        for from_table, rels in list(rels_by_table.items())[:10]:  # Limit to 10 relationships
            from_id = table_participants.get(from_table)
            if from_id:
                for rel in rels[:3]:  # Max 3 per table
                    to_table = rel.get('to_table')
                    to_id = table_participants.get(to_table)
                    from_col = rel.get('from_column')
                    to_col = rel.get('to_column')
                    
                    if to_id:
                        rel_label = f"FK: {from_col} → {to_col}" if from_col and to_col else "Foreign Key"
                        lines.append(f"    {from_id}->>{to_id}: \"{rel_label}\"")
                        step += 1
        
        if len(relationships) > 10:
            lines.append("    Note over User: \"... more relationships ...\"")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_code_architecture_diagram(self) -> str:
        """Generate high-level architecture diagram in clean, readable Mermaid.js format.
        
        For SQL: shows detailed database schema with all columns and relationships.
        
        Returns:
            Mermaid diagram code as string in clean format matching user requirements
        """
        language = self.parse_result.get('language', 'python').lower()
        
        # Handle SQL language - show detailed schema
        if language == 'sql':
            return self._generate_sql_detailed_architecture_diagram()
        
        lines = ["```mermaid", "graph TD"]
        lines.append("")
        
        # Module node (top-level) with styling
        module_id = "MODULE"
        lines.append(f"    {module_id}[\"📄 Module\"]")
        lines.append(f"    style {module_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        lines.append("")
        
        # Get top-level functions (not nested, not methods)
        top_level_funcs = [f for f in self.functions if not f.get('is_nested', False)]
        
        # Create mappings for reliable node ID lookups
        class_node_map = {}  # class_name -> node_id
        func_node_map = {}  # func_name -> node_id
        
        # Add all classes - simple format, no extra comments
        if self.classes:
            for cls in self.classes:
                class_name = cls['name']
                class_id = f"CLASS_{self._sanitize_id(class_name)}"
                class_node_map[class_name] = class_id
                class_label = f"🏛️ {class_name}"
                lines.append(f"    {module_id} --> {class_id}[\"{class_label}\"]")
                lines.append(f"    style {class_id} fill:#e3f2fd,stroke:#2196F3,stroke-width:2px")
        
        # Add all top-level functions - simple format, orange color
        if top_level_funcs:
            for func in top_level_funcs:
                func_name = func['name']
                func_id = f"FUNC_{self._sanitize_id(func_name)}"
                func_node_map[func_name] = func_id
                func_label = f"⚙️ {func_name}()"
                lines.append(f"    {module_id} --> {func_id}[\"{func_label}\"]")
                lines.append(f"    style {func_id} fill:#fff3e0,stroke:#f57c00,stroke-width:2px")
        
        # Track relationships to avoid duplicates
        relationships = set()
        
        # Add Key Relationships section
        lines.append("")
        lines.append("    %% Key Relationships")
        lines.append("")
        
        # 1. Class Inheritance Relationships
        for cls in self.classes:
            if cls.get('bases'):
                class_name = cls['name']
                class_id = class_node_map.get(class_name)
                
                for base in cls['bases']:
                    # Extract base class name (handle cases like "module.BaseClass")
                    base_name = base.split('.')[-1]
                    
                    # Check if base class is in our classes (not external)
                    base_class_id = class_node_map.get(base_name)
                    
                    if base_class_id and class_id:
                        rel_key = (class_id, base_class_id, 'inherits')
                        if rel_key not in relationships:
                            relationships.add(rel_key)
                            lines.append(f"    {class_id} -.->|inherits| {base_class_id}")
        
        # 2. Functions -> Classes (from class instantiations)
        for inst in self.class_instantiations:
            caller = inst['caller']
            class_name = inst['class_name']
        
            # Get caller ID (can be function or method)
            caller_id = None
            if '.' in caller:
                # It's a method, get the class
                class_name_from_caller = caller.split('.')[0]
                caller_id = class_node_map.get(class_name_from_caller)
            else:
                # It's a function
                caller_id = func_node_map.get(caller)
            
            # Get class ID
            target_class_id = class_node_map.get(class_name)
            
            if caller_id and target_class_id and caller_id != target_class_id:
                rel_key = (caller_id, target_class_id)
                if rel_key not in relationships:
                    relationships.add(rel_key)
                    lines.append(f"    {caller_id} --> {target_class_id}")
        
        # 3. Functions -> Functions (from function calls)
        for call in self.function_calls:
            caller = call['caller']
            callee = call['callee']
            
            # Get caller ID (only top-level functions)
            if '.' in caller:
                # It's a method, skip for now (we focus on top-level)
                continue
            
            caller_id = func_node_map.get(caller)
            
            # Get callee ID (only if it's a top-level function)
            if '.' in callee:
                # It's a method call or external, skip
                continue
            
            callee_id = func_node_map.get(callee)
            
            if caller_id and callee_id and caller_id != callee_id:
                rel_key = (caller_id, callee_id)
                if rel_key not in relationships:
                    relationships.add(rel_key)
                    lines.append(f"    {caller_id} --> {callee_id}")
        
        lines.append("")
        lines.append("```")
        return "\n".join(lines)
    
    def _sanitize_id(self, name: str) -> str:
        """Sanitize a name to be used as a Mermaid node ID."""
        # Replace spaces, dots, dashes with underscores, and remove special chars
        return name.replace(' ', '_').replace('.', '_').replace('-', '_').replace('/', '_')
    
    def _is_valid_participant(self, name: str) -> bool:
        """Check if a name represents a valid participant (function or class).
        
        Filters out:
        - Variables (not functions/classes)
        - Attribute accesses that aren't method calls
        - Simple expressions
        
        Args:
            name: Name to check
            
        Returns:
            True if name is a valid function or class
        """
        # Check if it's a known function (top-level or nested)
        if any(f['name'] == name for f in self.functions):
            return True
        
        # Check if it's a known class
        if any(c['name'] == name for c in self.classes):
            return True
        
        # For names with dots, check if the first part is a class
        # (e.g., "ClassName.method" - ClassName is the participant)
        if '.' in name:
            parts = name.split('.')
            if len(parts) >= 1:
                first_part = parts[0]
                # Check if the first part is a known class
                if any(c['name'] == first_part for c in self.classes):
                    return True
                # Check if the first part is a known function (for function.method patterns)
                if any(f['name'] == first_part for f in self.functions):
                    return True
        
        # Not a valid participant (likely a variable or invalid reference)
        return False
    
    def _is_valid_call(self, call: Dict) -> bool:
        """Check if a call should be included in the sequence diagram.
        
        Filters out:
        - Calls that are just attribute accesses (not method calls)
        - Calls where callee is just a variable (not a function/class)
        - Simple expressions
        - Calls where neither caller nor callee are valid participants
        
        Args:
            call: Call dictionary with 'caller', 'callee', 'line'
            
        Returns:
            True if call should be included
        """
        callee = call.get('callee', '')
        caller = call.get('caller', '')
        
        # Skip empty callees
        if not callee:
            return False
        
        # Both caller and callee must be valid participants
        caller_valid = self._is_valid_participant(caller.split('.')[0] if '.' in caller else caller)
        callee_valid = self._is_valid_participant(callee.split('.')[0] if '.' in callee else callee)
        
        if not caller_valid or not callee_valid:
            return False
        
        # For method calls (with dot notation), verify it's a real method call
        if '.' in callee:
            parts = callee.split('.')
            if len(parts) >= 2:
                class_or_obj_name = parts[0]
                method_name = parts[1]
                
                # Check if it's a method on a known class
                if any(c['name'] == class_or_obj_name for c in self.classes):
                    # Prefer to verify method exists, but include if class exists
                    for cls in self.classes:
                        if cls['name'] == class_or_obj_name:
                            methods = cls.get('methods', [])
                            # If method exists, definitely include
                            if any(m['name'] == method_name for m in methods):
                                return True
                    # Class exists, include the call (method might be dynamically added)
                    return True
                
                # For external calls (e.g., obj.method()), only include if obj is from a known class
                # This is a heuristic - we're more conservative
                return False
        
        # For simple function calls, check if callee is a known function
        if callee in [f['name'] for f in self.functions]:
            return True
        
        # If we get here, it's likely not a valid call
        return False
    
    def generate_sequence_diagram(self) -> str:
        """Generate Mermaid sequence diagram showing function call sequences.
        
        This method filters out noise to produce clean, readable diagrams:
        - Only includes actual functions and classes as participants (not variables)
        - Filters out attribute accesses, assignments, and simple expressions
        - Limits participants and calls for large codebases
        - Focuses on meaningful interactions between functions/classes
        
        For SQL: shows data flow through foreign key relationships.
        
        Returns:
            Mermaid diagram code as string
        """
        language = self.parse_result.get('language', 'python').lower()
        
        # Handle SQL language - show data flow through relationships
        if language == 'sql':
            return self._generate_sql_sequence_diagram()
        
        if not self.function_calls and not self.method_calls:
            # Generate sequence diagram based on available code elements
            return self._generate_structure_based_sequence()
        
        lines = ["```mermaid", "sequenceDiagram"]
        lines.append("    autonumber")
        
        # Collect all participants with their types
        participants = {}  # name -> type (class/function)
        
        # Add top-level functions as participants
        top_level_funcs = [f for f in self.functions if not f.get('is_nested', False)]
        for func in top_level_funcs:
            participants[func['name']] = 'function'
        
        # Add classes as participants
        for cls in self.classes:
            participants[cls['name']] = 'class'
        
        # Filter and add callers and callees from function calls
        # Only include if they're valid participants (functions/classes, not variables)
        for call in self.function_calls:
            if not self._is_valid_call(call):
                continue
                
            caller = call['caller']
            callee = call['callee']
            
            # Extract class/function name from caller
            if '.' in caller:
                caller_name = caller.split('.')[0]
                if caller_name not in participants and self._is_valid_participant(caller_name):
                    participants[caller_name] = 'class' if any(c['name'] == caller_name for c in self.classes) else 'function'
            else:
                if caller not in participants and self._is_valid_participant(caller):
                    participants[caller] = 'function'
            
            # Extract class/function name from callee
            if '.' in callee:
                callee_parts = callee.split('.')
                if len(callee_parts) >= 2:
                    callee_name = callee_parts[0]
                    if callee_name not in participants and self._is_valid_participant(callee_name):
                        participants[callee_name] = 'class' if any(c['name'] == callee_name for c in self.classes) else 'function'
            else:
                if callee not in participants and self._is_valid_participant(callee):
                    participants[callee] = 'function'
        
        # Add participants with descriptive labels
        participant_list = sorted(list(participants.keys()))
        
        # For large codebases, limit participants more aggressively
        # Only include the most important participants (entry points, main classes/functions)
        if len(participant_list) > 10:
            # Prioritize: main/entry functions, then classes, then other functions
            prioritized = []
            for p in participant_list:
                p_lower = p.lower()
                if any(keyword in p_lower for keyword in ['main', 'run', 'start', 'entry', 'app', 'init']):
                    prioritized.insert(0, p)
                elif participants.get(p) == 'class':
                    prioritized.append(p)
                else:
                    prioritized.append(p)
            participant_list = prioritized[:10]  # Limit to 10 for readability
        
        participant_map = {}  # short name -> full name for diagram
        
        # Create better short names (like M, SD, PC in the example)
        used_short_names = set()
        
        for i, participant in enumerate(participant_list):
            # Create short alias - try to use meaningful abbreviations
            short_name = None
            
            # Try common abbreviations first
            abbrev_map = {
                'main': 'M', 'run': 'R', 'start': 'S',
                'cart': 'CART', 'product': 'PC', 'catalog': 'CAT',
                'phone': 'P', 'laptop': 'L', 'device': 'D',
                'log': 'LOG', 'tax': 'TAX', 'email': 'E',
                'shopping': 'SD', 'demo': 'DEM'
            }
            
            participant_lower = participant.lower()
            for key, abbrev in abbrev_map.items():
                if key in participant_lower:
                    short_name = abbrev
                    break
            
            # If no abbreviation found, create one
            if not short_name:
                # Use first letters of words or first 3-4 chars
                words = participant.replace('_', ' ').split()
                if len(words) > 1:
                    short_name = ''.join([w[0].upper() for w in words[:3]])
                else:
                    short_name = participant[:4].upper()
            
            # Ensure uniqueness
            original_short = short_name
            counter = 1
            while short_name in used_short_names:
                short_name = f"{original_short}{counter}"
                counter += 1
            
            used_short_names.add(short_name)
            participant_map[participant] = short_name
            
            # Create descriptive label
            p_type = participants[participant]
            if p_type == 'class':
                label = f"{participant}"
            else:
                # For functions, show with parentheses
                label = f"{participant}()"
            
            lines.append(f"    participant {short_name} as \"{label}\"")
        
        # Build comprehensive call sequence with context
        all_calls = []
        
        # Process function calls - filter out invalid ones
        for call in self.function_calls:
            # Skip invalid calls (variables, assignments, simple expressions)
            if not self._is_valid_call(call):
                continue
                
            caller = call['caller']
            callee = call['callee']
            line = call['line']
            
            # Extract participant names
            if '.' in caller:
                caller_participant = caller.split('.')[0]
                caller_method = '.'.join(caller.split('.')[1:])
            else:
                caller_participant = caller
                caller_method = None
            
            if '.' in callee:
                callee_parts = callee.split('.')
                if len(callee_parts) >= 2:
                    callee_participant = callee_parts[0]
                    callee_method = callee_parts[1]
                else:
                    callee_participant = callee
                    callee_method = callee
            else:
                callee_participant = callee
                callee_method = callee
            
            # Only include if both participants are in our list and are valid
            if (caller_participant in participant_list and 
                callee_participant in participant_list and
                self._is_valid_participant(caller_participant) and
                self._is_valid_participant(callee_participant)):
                all_calls.append({
                    'caller': caller_participant,
                    'target': callee_participant,
                    'method': callee_method,
                    'line': line,
                    'type': 'function_call'
                })
        
        # Process method calls - these are generally valid
        for method_call in self.method_calls:
            caller = method_call['caller']
            target_class = method_call['class_name']
            method = method_call['method']
            line = method_call['line']
            
            if '.' in caller:
                caller_participant = caller.split('.')[0]
            else:
                caller_participant = caller
            
            # Only include if both participants are valid and in our list
            if (caller_participant in participant_list and 
                target_class in participant_list and
                self._is_valid_participant(caller_participant) and
                self._is_valid_participant(target_class)):
                all_calls.append({
                    'caller': caller_participant,
                    'target': target_class,
                    'method': method,
                    'line': line,
                    'type': 'method_call'
                })
        
        # Sort all calls by line number to show execution order
        all_calls.sort(key=lambda x: x['line'])
        
        # Group calls to identify loops and patterns
        call_groups = {}
        for call in all_calls[:30]:  # Limit to 30 calls
            caller = call['caller']
            if caller not in call_groups:
                call_groups[caller] = []
            call_groups[caller].append(call)
        
        # Generate sequence diagram with detailed interactions
        processed_calls = set()
        call_count = 0
        
        # Start with main/entry point
        main_participant = None
        if participant_list:
            # Find a likely main function or first function
            for p in participant_list:
                if 'main' in p.lower() or p.lower() in ['main', 'run', 'start']:
                    main_participant = p
                    break
            if not main_participant:
                main_participant = participant_list[0]
        
        # Find loop patterns first
        call_patterns = {}
        for call in all_calls:
            pattern = (call['caller'], call['target'], call['method'])
            if pattern not in call_patterns:
                call_patterns[pattern] = []
            call_patterns[pattern].append(call)
        
        # Identify loops (patterns that repeat 3+ times)
        loop_patterns = {pattern: calls for pattern, calls in call_patterns.items() if len(calls) >= 3}
        loop_processed = set()
        
        # Generate sequence in execution order with loops
        i = 0
        while i < len(all_calls) and call_count < 30:
            call = all_calls[i]
            pattern = (call['caller'], call['target'], call['method'])
            
            # Check if this pattern is a loop and hasn't been processed
            if pattern in loop_patterns and pattern not in loop_processed:
                # Process as a loop
                caller = call['caller']
                target = call['target']
                method = call['method']
                caller_short = participant_map.get(caller, caller)
                target_short = participant_map.get(target, target)
                
                # Determine loop description based on context
                loop_desc = "Each item"
                if participants.get(target) == 'class':
                    # Try to make it more descriptive
                    if 'product' in target.lower() or 'item' in target.lower():
                        loop_desc = "Each item in catalog"
                    elif 'device' in target.lower():
                        loop_desc = "Each device"
                    else:
                        loop_desc = f"Each {target.lower()}"
                elif 'for' in method.lower() or 'each' in method.lower() or 'loop' in method.lower():
                    loop_desc = "Each iteration"
                elif 'list' in method.lower() or 'items' in method.lower():
                    loop_desc = "Each item in list"
                
                # Add loop block
                lines.append(f"    loop \"{loop_desc}\"")
                
                # Add calls within loop (show representative iterations)
                loop_calls = sorted(loop_patterns[pattern], key=lambda x: x['line'])
                iterations_shown = min(3, len(loop_calls))  # Show up to 3 iterations
                
                for j in range(iterations_shown):
                    if call_count >= 25:
                        break
                    lines.append(f"        {caller_short}->>{target_short}: \"{method}()\"")
                    
                    # Add return arrow with descriptive response
                    if participants.get(target) == 'class':
                        # Try to determine return type
                        if 'detail' in method.lower():
                            lines.append(f"        {target_short}-->>{caller_short}: \"specs()\"")
                        elif 'get' in method.lower() or 'fetch' in method.lower():
                            lines.append(f"        {target_short}-->>{caller_short}: \"data\"")
                        else:
                            lines.append(f"        {target_short}-->>{caller_short}: \"result\"")
                    else:
                        lines.append(f"        {target_short}-->>{caller_short}: \"return value\"")
                    
                    call_count += 1
                
                lines.append(f"    end")
                loop_processed.add(pattern)
                
                # Skip the individual calls that were in the loop
                skip_count = len(loop_patterns[pattern])
                i += skip_count
                continue
            
            # Regular call (not in a processed loop)
            if pattern not in loop_processed:
                caller = call['caller']
                target = call['target']
                method = call['method']
                
                # Skip self-calls unless they're method calls
                if caller == target and call['type'] != 'method_call':
                    i += 1
                    continue
                
                caller_short = participant_map.get(caller, caller)
                target_short = participant_map.get(target, target)
                
                # Create descriptive message with context
                if call['type'] == 'method_call':
                    message = f"{method}()"
                    # Add parameters if it's a constructor or important method
                    if method == '__init__' or 'new' in method.lower():
                        # Try to get class name for constructor
                        if participants.get(target) == 'class':
                            message = f"new {target}()"
                elif method and method != target:
                    message = f"{method}()"
                else:
                    message = f"{target}()"
                
                # Add call
                lines.append(f"    {caller_short}->>{target_short}: \"{message}\"")
                
                # Add return arrow with descriptive response
                if call['type'] == 'method_call' and participants.get(target) == 'class':
                    # Determine return type based on method name
                    method_lower = method.lower()
                    if 'detail' in method_lower or 'spec' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"specs()\"")
                    elif 'get' in method_lower or 'fetch' in method_lower or 'return' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"data\"")
                    elif 'valid' in method_lower or 'check' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"true\"")
                    elif 'sum' in method_lower or 'total' in method_lower or 'calculate' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"final_price\"")
                    elif 'new' in method_lower or '__init__' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"instance\"")
                    else:
                        lines.append(f"    {target_short}-->>{caller_short}: \"result\"")
                elif participants.get(target) == 'function':
                    # For function calls, show return
                    func_name = target.lower()
                    if 'catalog' in func_name or 'list' in func_name:
                        lines.append(f"    {target_short}-->>{caller_short}: \"[Device List]\"")
                    elif 'valid' in func_name or 'check' in func_name:
                        lines.append(f"    {target_short}-->>{caller_short}: \"true\"")
                    else:
                        lines.append(f"    {target_short}-->>{caller_short}: \"return value\"")
                
                call_count += 1
                loop_processed.add(pattern)
            
            i += 1
        
        # Add final return if main function exists
        if main_participant and call_count > 0:
            main_short = participant_map.get(main_participant, main_participant)
            # Check if main called something that should return
            for call in all_calls:
                if call['caller'] == main_participant:
                    target_short = participant_map.get(call['target'], call['target'])
                    if participants.get(call['target']) == 'function':
                        lines.append(f"    {target_short}-->>{main_short}: \"return\"")
                    break
        
        # If no calls were added, show a message
        if call_count == 0:
            if main_participant:
                main_short = participant_map.get(main_participant, main_participant)
                lines.append(f"    {main_short}->>{main_short}: \"No interactions detected\"")
                lines.append(f"    Note over {main_short}: Add function/method calls to see sequence")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_dependency_diagram(self) -> str:
        """Generate Mermaid dependency diagram showing module/import relationships.
        
        Returns:
            Mermaid diagram code as string
        """
        if not self.imports:
            return "```mermaid\ngraph TD\n    A[\"📦 No Imports Found\"] --> B[\"Add imports to your code\"]\n    style A fill:#e8f4f8\n    style B fill:#fff4e6\n```"
        
        lines = ["```mermaid", "graph TD"]
        lines.append("    direction TB")
        
        # Group imports by module
        modules = set()
        import_details = {}
        for imp in self.imports:
            if imp['type'] == 'import':
                module = imp['module'].split('.')[0]
                modules.add(module)
                if module not in import_details:
                    import_details[module] = []
                import_details[module].append(imp['module'])
            elif imp['type'] == 'from_import' and imp['module']:
                module = imp['module'].split('.')[0]
                modules.add(module)
                if module not in import_details:
                    import_details[module] = []
                import_details[module].append(f"{imp['module']}.{imp['name']}")
        
        # Current module (your code)
        current_module = "CurrentModule"
        lines.append(f"    {current_module}[\"📄 Your Code\"]")
        lines.append(f"    style {current_module} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        
        # Add modules as nodes with better labels
        module_list = sorted(list(modules))[:12]  # Limit to 12 for readability
        for module in module_list:
            module_id = module.replace('.', '_').replace('-', '_')
            count = len(import_details.get(module, []))
            label = f"📚 {module}" if count > 1 else f"📦 {module}"
            lines.append(f"    {module_id}[\"{label}\"]")
            lines.append(f"    style {module_id} fill:#fff4e6,stroke:#ff9800")
            lines.append(f"    {current_module} -->|imports| {module_id}")
        
        if len(modules) > 12:
            lines.append(f"    More[\"... and {len(modules) - 12} more modules\"]")
            lines.append(f"    style More fill:#f5f5f5,stroke:#999")
            lines.append(f"    {current_module} --> More")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_flowchart(self, function_name: str = None) -> str:
        """Generate flowchart diagram.
        
        For JavaScript: generates flowchart for the first function.
        For SQL: generates flow diagram showing foreign key relationships.
        For Python: generates control flow diagram.
        """
        language = self.parse_result.get('language', 'python').lower()
        
        if language == 'sql':
            return self._generate_sql_flow_diagram()
        elif language == 'javascript':
            return self._generate_javascript_flowchart()
        else:
            return self._generate_python_flowchart(function_name)
    
    def _generate_python_flowchart(self, function_name: str = None) -> str:
        """Generate Mermaid flowchart for a specific function or all functions.
        
        Args:
            function_name: Name of function to generate flowchart for. If None, generates for first function with control flow.
            
        Returns:
            Mermaid flowchart code as string
        """
        # Get functions to process
        if function_name:
            funcs_to_process = [f for f in self.functions if f['name'] == function_name]
        else:
            # Get top-level functions (not nested, not methods)
            funcs_to_process = [f for f in self.functions if not f.get('is_nested', False)]
        
        if not funcs_to_process:
            # Generate flowchart based on available code elements
            return self._generate_structure_based_flowchart()
        
        # Find function with most control flow (including function calls)
        funcs_with_flow = []
        for func in funcs_to_process:
            func_name = func['name']
            func_flow = [cf for cf in self.control_flow if cf.get('function') == func_name]
            if func_flow:
                funcs_with_flow.append((func, len(func_flow)))
        
        if funcs_with_flow:
            # Sort by control flow count and take the first
            funcs_with_flow.sort(key=lambda x: x[1], reverse=True)
            return self._generate_single_flowchart(funcs_with_flow[0][0])
        else:
            # No control flow found - check if there are any functions with calls
            # If a function exists but has no control flow, still show a basic flowchart
            if funcs_to_process:
                return self._generate_single_flowchart(funcs_to_process[0])
            # No functions at all
            return "```mermaid\nflowchart TD\n    A[Functions found] --> B[No control flow structures detected]\n    B --> C[Add if/else, loops, etc. to see flowcharts]\n```"
    
    def _generate_javascript_flowchart(self) -> str:
        """Generate flowchart for JavaScript - uses the first function from parse_code_auto output."""
        functions = self.parse_result.get('functions', [])
        
        if not functions:
            # Generate flowchart based on available code elements
            return self._generate_structure_based_flowchart()
        
        # Get the FIRST function from parse_code_auto output
        first_func = functions[0]
        func_name = first_func.get('name', 'function')
        params = first_func.get('parameters', [])
        is_async = first_func.get('is_async', False)
        
        lines = ["```mermaid", "flowchart TD"]
        
        # Start node
        start_id = "Start"
        func_label = f"▶️ Start: {func_name}"
        if is_async:
            func_label += " (async)"
        if params:
            param_str = ', '.join(params[:3])
            if len(params) > 3:
                param_str += f", +{len(params) - 3}"
            func_label += f"\\n({param_str})"
        
        lines.append(f"    {start_id}([\"{func_label}\"])")
        lines.append(f"    style {start_id} fill:#e8f4f8,stroke:#2196F3,stroke-width:3px")
        
        # Process node (simplified - JavaScript parser doesn't extract control flow yet)
        process_id = "Process"
        lines.append(f"    {start_id} --> {process_id}[\"⚙️ Function Body\"]")
        lines.append(f"    style {process_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:2px")
        
        # Return/End node
        end_id = "End"
        lines.append(f"    {process_id} --> {end_id}([\"🏁 End: {func_name}\"])")
        lines.append(f"    style {end_id} fill:#ffebee,stroke:#f44336,stroke-width:3px")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_sql_flow_diagram(self) -> str:
        """Generate flow diagram for SQL showing foreign key relationships."""
        tables = self.parse_result.get('tables', [])
        relationships = self.parse_result.get('relationships', [])
        
        if not tables:
            return "```mermaid\nflowchart TD\n    A[No tables found] --> B[Add CREATE TABLE statements to generate flow diagram]\n```"
        
        if not relationships:
            return "```mermaid\nflowchart TD\n    A[Tables found] --> B[No foreign key relationships detected]\n    B --> C[Add FOREIGN KEY constraints to see relationships]\n```"
        
        lines = ["```mermaid", "flowchart TD"]
        lines.append("    direction TB")
        
        # Create nodes for each table
        table_nodes = {}
        for table in tables:
            table_name = table['name']
            table_id = f"T_{table_name}".replace(' ', '_')
            table_nodes[table_name] = table_id
            
            # Build table label with column count
            col_count = len(table.get('columns', []))
            table_label = f"📊 {table_name}\\n({col_count} columns)"
            
            lines.append(f"    {table_id}[\"{table_label}\"]")
            lines.append(f"    style {table_id} fill:#e3f2fd,stroke:#2196F3,stroke-width:2px")
        
        # Add relationships (foreign keys)
        for rel in relationships:
            from_table = rel.get('from_table')
            to_table = rel.get('to_table')
            from_column = rel.get('from_column')
            to_column = rel.get('to_column')
            
            if from_table in table_nodes and to_table in table_nodes:
                from_id = table_nodes[from_table]
                to_id = table_nodes[to_table]
                
                # Create relationship label
                rel_label = f"{from_column} → {to_column}"
                if len(rel_label) > 30:
                    rel_label = f"{from_column[:15]}... → {to_column[:15]}..."
                
                lines.append(f"    {from_id} -->|{rel_label}| {to_id}")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _add_call_group_to_flowchart(self, lines: List[str], call_group: List[Dict], current_node: str, start_node_id: int) -> str:
        """Add a group of consecutive function calls to flowchart - show only essential ones."""
        # Limit to 3-4 most important calls to keep flowchart concise
        important_calls = call_group[:4] if len(call_group) > 4 else call_group
        
        last_node = current_node
        for i, call in enumerate(important_calls):
            action_label = call.get('action_label', call.get('call_label', 'Call function'))
            # Truncate long labels
            if len(action_label) > 25:
                action_label = action_label[:22] + "..."
            
            call_id = f"CALL{start_node_id + i}"
            lines.append(f"    {last_node} --> {call_id}[\"⚙️ {action_label}\"]")
            lines.append(f"    style {call_id} fill:#e1bee7,stroke:#9c27b0,stroke-width:2px")
            last_node = call_id
        
        # If there were more calls, indicate with ellipsis
        if len(call_group) > 4:
            more_id = f"CALL_MORE{start_node_id + len(important_calls)}"
            lines.append(f"    {last_node} --> {more_id}[\"⚙️ ... {len(call_group) - 4} more calls\"]")
            lines.append(f"    style {more_id} fill:#f3e5f5,stroke:#9c27b0,stroke-width:1px")
            last_node = more_id
        
        return last_node
    
    def _generate_single_flowchart(self, func_info: Dict) -> str:
        """Generate concise flowchart for a single function showing essential flow."""
        func_name = func_info['name']
        lines = ["```mermaid", "flowchart TD"]
        
        # Get control flow for this function
        func_flow = [cf for cf in self.control_flow if cf.get('function') == func_name]
        
        # Start node with better label
        start_id = "Start"
        lines.append(f"    {start_id}([\"▶️ Start: {func_name}\"])")
        lines.append(f"    style {start_id} fill:#e8f4f8,stroke:#2196F3,stroke-width:3px")
        
        # Process control flow structures - optimize for concise representation
        node_id = 1
        current_node = start_id
        
        # Group consecutive function calls to avoid clutter
        call_group = []
        
        for flow in sorted(func_flow, key=lambda x: x.get('line', 0)):
            flow_type = flow.get('type')
            
            if flow_type == 'call':
                # Collect consecutive calls to group them
                call_group.append(flow)
            else:
                # Process any accumulated calls first
                if call_group:
                    current_node = self._add_call_group_to_flowchart(lines, call_group, current_node, node_id)
                    node_id += min(len(call_group), 4) + (1 if len(call_group) > 4 else 0)
                    call_group = []
                
                # Process non-call flow structures
                if flow_type == 'with':
                    # With statement - concise: Enter → Exit
                    items = flow.get('items', [])
                    if items:
                        with_label = items[0].get('label', 'Enter context')
                        context_name = with_label.replace('Enter ', '') if with_label.startswith('Enter ') else with_label
                    else:
                        context_name = "context"
                        with_label = f"Enter {context_name}"
                    
                    # Truncate long labels
                    if len(context_name) > 20:
                        context_name = context_name[:17] + "..."
                    
                    enter_id = f"WITH{node_id}"
                    exit_id = f"WITH_EXIT{node_id}"
                    
                    lines.append(f"    {current_node} --> {enter_id}[\"🔓 {with_label}\"]")
                    lines.append(f"    style {enter_id} fill:#fff3e0,stroke:#ff9800,stroke-width:2px")
                    lines.append(f"    {enter_id} --> {exit_id}[\"🔒 Exit {context_name}\"]")
                    lines.append(f"    style {exit_id} fill:#fff3e0,stroke:#ff9800,stroke-width:2px")
                    current_node = exit_id
                    node_id += 1
                
                elif flow_type == 'try':
                    # Try/except block - concise representation
                    exceptions = flow.get('exceptions', ['Exception'])
                    has_finally = flow.get('has_finally', False)
                    end_try_id = f"END_TRY{node_id}"
                    
                    # Limit to 4 exception types to keep it concise
                    if len(exceptions) > 4:
                        exceptions = exceptions[:3] + ['...']
                    
                    try_id = f"TRY{node_id}"
                    lines.append(f"    {current_node} --> {try_id}[\"⚠️ Try\"]")
                    lines.append(f"    style {try_id} fill:#fff3e0,stroke:#ff9800,stroke-width:2px")
                    
                    # Add exception handlers - simplified
                    except_nodes = []
                    for i, exc_type in enumerate(exceptions):
                        if exc_type == '...':
                            except_id = f"EXCEPT_MORE{node_id}"
                            lines.append(f"    {try_id} -->|\"❌ ...\"| {except_id}[\"⚠️ More exceptions\"]")
                            lines.append(f"    style {except_id} fill:#ffebee,stroke:#f44336,stroke-width:2px")
                            except_nodes.append(except_id)
                        else:
                            except_id = f"EXCEPT{i+1}_{node_id}"
                            except_label = f"Except {exc_type}"
                            # Truncate long exception names
                            if len(except_label) > 20:
                                except_label = except_label[:17] + "..."
                            lines.append(f"    {try_id} -->|\"❌ {exc_type}\"| {except_id}[\"⚠️ {except_label}\"]")
                            lines.append(f"    style {except_id} fill:#ffebee,stroke:#f44336,stroke-width:2px")
                            except_nodes.append(except_id)
                    
                    # Merge exception handlers
                    if except_nodes:
                        if has_finally:
                            finally_id = f"FINALLY{node_id}"
                            lines.append(f"    {try_id} -->|\"✅ Success\"| {finally_id}[\"✅ Finally\"]")
                            lines.append(f"    style {finally_id} fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px")
                            for except_node in except_nodes:
                                lines.append(f"    {except_node} --> {finally_id}")
                            lines.append(f"    {finally_id} --> {end_try_id}[\"➡️ Continue\"]")
                        else:
                            lines.append(f"    {try_id} -->|\"✅ Success\"| {end_try_id}[\"➡️ Continue\"]")
                            for except_node in except_nodes:
                                lines.append(f"    {except_node} --> {end_try_id}")
                    else:
                        # No exception handlers
                        if has_finally:
                            finally_id = f"FINALLY{node_id}"
                            lines.append(f"    {try_id} --> {finally_id}[\"✅ Finally\"]")
                            lines.append(f"    style {finally_id} fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px")
                            lines.append(f"    {finally_id} --> {end_try_id}[\"➡️ Continue\"]")
                        else:
                            lines.append(f"    {try_id} --> {end_try_id}[\"➡️ Continue\"]")
                    
                    lines.append(f"    style {end_try_id} fill:#f3e5f5,stroke:#9c27b0")
                    current_node = end_try_id
                    node_id += 1
                
                elif flow_type == 'if':
                    condition = flow.get('condition', 'condition')
                    # Truncate long conditions
                    if len(condition) > 30:
                        condition = condition[:27] + "..."
                    if_id = f"IF{node_id}"
                    true_id = f"TRUE{node_id}"
                    false_id = f"FALSE{node_id}"
                    end_if_id = f"ENDIF{node_id}"
                    
                    lines.append(f"    {current_node} --> {if_id}{{\"{condition}\"}}")
                    lines.append(f"    style {if_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
                    lines.append(f"    {if_id} -->|\"✅ True\"| {true_id}[\"📝 If Body\"]")
                    lines.append(f"    style {true_id} fill:#e8f5e9,stroke:#4caf50")
                    
                    if flow.get('has_else'):
                        lines.append(f"    {if_id} -->|\"❌ False\"| {false_id}[\"📝 Else Body\"]")
                        lines.append(f"    style {false_id} fill:#e8f5e9,stroke:#4caf50")
                        lines.append(f"    {true_id} --> {end_if_id}[\"➡️ Continue\"]")
                        lines.append(f"    {false_id} --> {end_if_id}")
                    else:
                        lines.append(f"    {if_id} -->|\"❌ False\"| {end_if_id}[\"➡️ Continue\"]")
                        lines.append(f"    {true_id} --> {end_if_id}")
                    
                    lines.append(f"    style {end_if_id} fill:#f3e5f5,stroke:#9c27b0")
                    current_node = end_if_id
                    node_id += 1
                
                elif flow_type == 'for':
                    target = flow.get('target', 'item')
                    iter_expr = flow.get('iter', 'iterable')
                    # Truncate long expressions
                    if len(iter_expr) > 25:
                        iter_expr = iter_expr[:22] + "..."
                    loop_id = f"LOOP{node_id}"
                    body_id = f"BODY{node_id}"
                    end_loop_id = f"ENDLOOP{node_id}"
                    
                    lines.append(f"    {current_node} --> {loop_id}{{\"🔄 for {target} in {iter_expr}\"}}")
                    lines.append(f"    style {loop_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
                    lines.append(f"    {loop_id} -->|\"✅ Has items\"| {body_id}[\"📝 Loop Body\"]")
                    lines.append(f"    style {body_id} fill:#e8f5e9,stroke:#4caf50")
                    lines.append(f"    {loop_id} -->|\"❌ No items\"| {end_loop_id}[\"➡️ Continue\"]")
                    lines.append(f"    {body_id} -->|\"↩️ Loop back\"| {loop_id}")
                    lines.append(f"    style {end_loop_id} fill:#f3e5f5,stroke:#9c27b0")
                    
                    current_node = end_loop_id
                    node_id += 1
                
                elif flow_type == 'while':
                    condition = flow.get('condition', 'condition')
                    # Truncate long conditions
                    if len(condition) > 30:
                        condition = condition[:27] + "..."
                    loop_id = f"WHILE{node_id}"
                    body_id = f"BODY{node_id}"
                    end_while_id = f"ENDWHILE{node_id}"
                    
                    lines.append(f"    {current_node} --> {loop_id}{{\"🔄 {condition}\"}}")
                    lines.append(f"    style {loop_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
                    lines.append(f"    {loop_id} -->|\"✅ True\"| {body_id}[\"📝 While Body\"]")
                    lines.append(f"    style {body_id} fill:#e8f5e9,stroke:#4caf50")
                    lines.append(f"    {loop_id} -->|\"❌ False\"| {end_while_id}[\"➡️ Continue\"]")
                    lines.append(f"    {body_id} -->|\"↩️ Loop back\"| {loop_id}")
                    lines.append(f"    style {end_while_id} fill:#f3e5f5,stroke:#9c27b0")
                    
                    current_node = end_while_id
                    node_id += 1
                
                elif flow_type == 'return':
                    return_id = f"RETURN{node_id}"
                    if flow.get('has_value'):
                        lines.append(f"    {current_node} --> {return_id}([\"↩️ Return with value\"])")
                    else:
                        lines.append(f"    {current_node} --> {return_id}([\"↩️ Return\"])")
                    lines.append(f"    style {return_id} fill:#ffebee,stroke:#f44336,stroke-width:2px")
                    lines.append(f"    {return_id} --> END([\"🏁 End\"])")
                    lines.append(f"    style END fill:#e8f4f8,stroke:#2196F3,stroke-width:3px")
                    current_node = None
                    node_id += 1
                    break
                
                elif flow_type == 'break':
                    break_id = f"BREAK{node_id}"
                    lines.append(f"    {current_node} --> {break_id}([Break])")
                    lines.append(f"    {break_id} --> END([End])")
                    current_node = None
                    node_id += 1
                    break
                
                elif flow_type == 'continue':
                    continue_id = f"CONTINUE{node_id}"
                    lines.append(f"    {current_node} --> {continue_id}([Continue])")
                    # Continue goes back to loop start - simplified for now
                    current_node = continue_id
                    node_id += 1
        
        # Process any remaining call group
        if call_group:
            current_node = self._add_call_group_to_flowchart(lines, call_group, current_node, node_id)
        
        # End node
        if current_node:
            lines.append(f"    {current_node} --> END([\"🏁 End\"])")
            lines.append(f"    style END fill:#e8f4f8,stroke:#2196F3,stroke-width:3px")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_structure_diagram(self) -> str:
        """Generate Mermaid structure diagram showing hierarchical code organization.
        
        Shows the overall structure: classes with methods, top-level functions,
        nested functions, and their relationships.
        For JavaScript: shows functions and classes.
        For SQL: shows tables and relationships.
        
        Returns:
            Mermaid diagram code as string
        """
        language = self.parse_result.get('language', 'python').lower()
        
        # Handle SQL language - show tables and relationships
        if language == 'sql':
            return self._generate_sql_structure_diagram()
        
        # Handle JavaScript and Python - show functions and classes
        # Even if no functions/classes, show other code elements
        has_code_elements = (
            self.classes or 
            self.functions or 
            self.parse_result.get('global_variables', []) or 
            self.parse_result.get('local_variables', []) or 
            self.imports or 
            self.parse_result.get('tables', [])
        )
        
        if not has_code_elements:
            return "```mermaid\ngraph TD\n    A[\"📦 No Code Structure Found\"] --> B[\"Add classes, functions, variables, or imports to your code\"]\n    style A fill:#e8f4f8\n    style B fill:#fff4e6\n```"
        
        lines = ["```mermaid", "graph TD"]
        lines.append("    direction TB")
        
        # Root node
        root_id = "ROOT"
        lang_label = "JavaScript" if language == 'javascript' else "Code"
        lines.append(f"    {root_id}[\"📄 {lang_label} Structure\"]")
        lines.append(f"    style {root_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        
        # Separate top-level functions and nested functions
        top_level_funcs = [f for f in self.functions if not f.get('is_nested', False)]
        nested_funcs = [f for f in self.functions if f.get('is_nested', False)]
        
        # Group functions by their parent (if nested)
        nested_by_parent = {}
        for func in nested_funcs:
            # Try to find parent - this is simplified, actual parent tracking would need parser enhancement
            parent = "Nested"
            nested_by_parent.setdefault(parent, []).append(func)
        
        # Add classes section
        if self.classes:
            classes_id = "CLASSES"
            lines.append(f"    {root_id} --> {classes_id}[\"🏛️ Classes ({len(self.classes)})\"]")
            lines.append(f"    style {classes_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
            
            for cls in self.classes:
                class_id = f"CLASS_{cls['name']}".replace(' ', '_')
                # Format class name with base classes: "ClassName(BaseClass)"
                if cls.get('bases'):
                    bases_str = ', '.join(cls['bases'][:2])
                    if len(cls['bases']) > 2:
                        bases_str += f", +{len(cls['bases']) - 2}"
                    class_label = f"📦 {cls['name']}({bases_str})"
                else:
                    class_label = f"📦 {cls['name']}"
                
                lines.append(f"    {classes_id} --> {class_id}[\"{class_label}\"]")
                lines.append(f"    style {class_id} fill:#e3f2fd,stroke:#2196F3")
                
                # Add methods
                methods = cls.get('methods', [])
                if methods:
                    methods_id = f"{class_id}_METHODS"
                    lines.append(f"    {class_id} --> {methods_id}[\"🔧 Methods ({len(methods)})\"]")
                    lines.append(f"    style {methods_id} fill:#f3e5f5,stroke:#9c27b0")
                    
                    # Show first 5 methods
                    for method in methods[:5]:
                        method_id = f"{class_id}_M_{method['name']}".replace(' ', '_')
                        method_label = method['name']
                        if method.get('is_async'):
                            method_label = f"🔁 {method_label}"
                        method_label += "()"
                        lines.append(f"    {methods_id} --> {method_id}[\"{method_label}\"]")
                        lines.append(f"    style {method_id} fill:#fce4ec,stroke:#e91e63")
                    
                    if len(methods) > 5:
                        more_id = f"{class_id}_MORE"
                        lines.append(f"    {methods_id} --> {more_id}[\"... {len(methods) - 5} more methods\"]")
                        lines.append(f"    style {more_id} fill:#f5f5f5,stroke:#999")
                
                # Add class variables
                class_vars = cls.get('class_variables', [])
                if class_vars:
                    vars_id = f"{class_id}_VARS"
                    lines.append(f"    {class_id} --> {vars_id}[\"📊 Class Variables ({len(class_vars)})\"]")
                    lines.append(f"    style {vars_id} fill:#e0f2f1,stroke:#009688")
                    
                    for var in class_vars[:3]:
                        var_id = f"{class_id}_VAR_{var['name']}".replace(' ', '_')
                        lines.append(f"    {vars_id} --> {var_id}[\"{var['name']}\"]")
                        lines.append(f"    style {var_id} fill:#b2dfdb,stroke:#00796b")
        
        # Add top-level functions section
        if top_level_funcs:
            funcs_id = "FUNCTIONS"
            lines.append(f"    {root_id} --> {funcs_id}[\"⚙️ Top-Level Functions ({len(top_level_funcs)})\"]")
            lines.append(f"    style {funcs_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
            
            for func in top_level_funcs[:10]:  # Limit to 10 for readability
                func_id = f"FUNC_{func['name']}".replace(' ', '_')
                func_label = func['name']
                if func.get('is_async'):
                    func_label = f"🔁 {func_label}"
                func_label += "()"
                
                # Add parameter count
                params = func.get('parameters', [])
                if params:
                    param_count = len([p for p in params if p != 'self'])
                    if param_count > 0:
                        func_label += f"\\n({param_count} params)"
                
                lines.append(f"    {funcs_id} --> {func_id}[\"{func_label}\"]")
                lines.append(f"    style {func_id} fill:#e8f5e9,stroke:#4caf50")
            
            if len(top_level_funcs) > 10:
                more_funcs_id = "MORE_FUNCS"
                lines.append(f"    {funcs_id} --> {more_funcs_id}[\"... {len(top_level_funcs) - 10} more functions\"]")
                lines.append(f"    style {more_funcs_id} fill:#f5f5f5,stroke:#999")
        
        # Add nested functions section if any
        if nested_funcs:
            nested_id = "NESTED"
            lines.append(f"    {root_id} --> {nested_id}[\"🔗 Nested Functions ({len(nested_funcs)})\"]")
            lines.append(f"    style {nested_id} fill:#f3e5f5,stroke:#9c27b0")
            
            for func in nested_funcs[:5]:  # Limit to 5
                nested_func_id = f"NESTED_{func['name']}".replace(' ', '_')
                func_label = func['name']
                if func.get('is_async'):
                    func_label = f"🔁 {func_label}"
                func_label += "()"
                lines.append(f"    {nested_id} --> {nested_func_id}[\"{func_label}\"]")
                lines.append(f"    style {nested_func_id} fill:#fce4ec,stroke:#e91e63")
            
            if len(nested_funcs) > 5:
                more_nested_id = "MORE_NESTED"
                lines.append(f"    {nested_id} --> {more_nested_id}[\"... {len(nested_funcs) - 5} more nested\"]")
                lines.append(f"    style {more_nested_id} fill:#f5f5f5,stroke:#999")
        
        # Add global variables section
        global_vars = self.parse_result.get('global_variables', [])
        if global_vars:
            globals_id = "GLOBALS"
            lines.append(f"    {root_id} --> {globals_id}[\"🌍 Global Variables ({len(global_vars)})\"]")
            lines.append(f"    style {globals_id} fill:#e0f2f1,stroke:#009688")
            
            for var in global_vars[:5]:  # Limit to 5
                var_id = f"GLOBAL_{var.get('name', 'var')}".replace(' ', '_')
                var_name = var.get('name', 'variable')
                lines.append(f"    {globals_id} --> {var_id}[\"{var_name}\"]")
                lines.append(f"    style {var_id} fill:#b2dfdb,stroke:#00796b")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_sql_structure_diagram(self) -> str:
        """Generate structure diagram for SQL showing tables and relationships.
        
        Returns:
            Mermaid diagram code as string
        """
        tables = self.parse_result.get('tables', [])
        relationships = self.parse_result.get('relationships', [])
        
        if not tables:
            return "```mermaid\ngraph TD\n    A[\"📦 No Tables Found\"] --> B[\"Add CREATE TABLE statements to your SQL\"]\n    style A fill:#e8f4f8\n    style B fill:#fff4e6\n```"
        
        lines = ["```mermaid", "graph TD"]
        lines.append("    direction TB")
        
        # Root node
        root_id = "ROOT"
        lines.append(f"    {root_id}[\"📊 Database Structure\"]")
        lines.append(f"    style {root_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        
        # Tables section
        tables_id = "TABLES"
        lines.append(f"    {root_id} --> {tables_id}[\"🗄️ Tables ({len(tables)})\"]")
        lines.append(f"    style {tables_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
        
        # Add each table
        for table in tables:
            table_name = table['name']
            table_id = f"TABLE_{table_name}".replace(' ', '_')
            columns = table.get('columns', [])
            
            lines.append(f"    {tables_id} --> {table_id}[\"📋 {table_name}\"]")
            lines.append(f"    style {table_id} fill:#e3f2fd,stroke:#2196F3,stroke-width:2px")
            
            # Add columns
            if columns:
                cols_id = f"{table_id}_COLS"
                lines.append(f"    {table_id} --> {cols_id}[\"📝 Columns ({len(columns)})\"]")
                lines.append(f"    style {cols_id} fill:#f3e5f5,stroke:#9c27b0")
                
                # Show columns with their types and constraints
                for col in columns[:10]:  # Limit to 10 columns
                    col_id = f"{table_id}_COL_{col['name']}".replace(' ', '_')
                    col_label = col['name']
                    
                    # Add type
                    if col.get('type'):
                        col_label += f"\\n{col['type']}"
                    
                    # Add constraints
                    constraints = []
                    if col.get('is_primary_key'):
                        constraints.append('PK')
                    if col.get('is_foreign_key'):
                        constraints.append('FK')
                    if col.get('is_unique'):
                        constraints.append('UNIQUE')
                    if col.get('is_not_null'):
                        constraints.append('NOT NULL')
                    
                    if constraints:
                        col_label += f"\\n[{', '.join(constraints)}]"
                    
                    lines.append(f"    {cols_id} --> {col_id}[\"{col_label}\"]")
                    lines.append(f"    style {col_id} fill:#fce4ec,stroke:#e91e63")
                
                if len(columns) > 10:
                    more_cols_id = f"{table_id}_MORE_COLS"
                    lines.append(f"    {cols_id} --> {more_cols_id}[\"... {len(columns) - 10} more columns\"]")
                    lines.append(f"    style {more_cols_id} fill:#f5f5f5,stroke:#999")
        
        # Add relationships section
        if relationships:
            rels_id = "RELATIONSHIPS"
            lines.append(f"    {root_id} --> {rels_id}[\"🔗 Relationships ({len(relationships)})\"]")
            lines.append(f"    style {rels_id} fill:#e0f2f1,stroke:#009688,stroke-width:2px")
            
            for rel in relationships[:10]:  # Limit to 10 relationships
                from_table = rel.get('from_table')
                to_table = rel.get('to_table')
                from_col = rel.get('from_column')
                to_col = rel.get('to_column')
                
                if from_table and to_table:
                    from_id = f"TABLE_{from_table}".replace(' ', '_')
                    to_id = f"TABLE_{to_table}".replace(' ', '_')
                    
                    # Only add relationship if both tables exist
                    if any(t['name'] == from_table for t in tables) and any(t['name'] == to_table for t in tables):
                        rel_label = f"{from_col} → {to_col}" if from_col and to_col else "→"
                        lines.append(f"    {from_id} -->|{rel_label}| {to_id}")
            
            if len(relationships) > 10:
                more_rels_id = "MORE_RELS"
                lines.append(f"    {rels_id} --> {more_rels_id}[\"... {len(relationships) - 10} more relationships\"]")
                lines.append(f"    style {more_rels_id} fill:#f5f5f5,stroke:#999")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_sql_detailed_architecture_diagram(self) -> str:
        """Generate detailed architecture diagram for SQL showing all tables, columns, and relationships."""
        tables = self.parse_result.get('tables', [])
        relationships = self.parse_result.get('relationships', [])
        
        if not tables:
            return "```mermaid\ngraph TD\n    A[\"📦 No Tables Found\"]\n    A --> B[\"Add CREATE TABLE statements to your SQL\"]\n    style A fill:#e8f4f8\n    style B fill:#fff4e6\n```"
        
        lines = ["```mermaid", "graph TD"]
        lines.append("    direction TB")
        
        # Root node
        root_id = "SCHEMA"
        lines.append(f"    {root_id}[\"🗄️ Database Schema\"]")
        lines.append(f"    style {root_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        
        # Create detailed table nodes
        table_nodes = {}
        for table in tables:
            table_name = table['name']
            table_id = f"T_{table_name}".replace(' ', '_').replace('-', '_')
            table_nodes[table_name] = table_id
            
            columns = table.get('columns', [])
            
            # Build detailed table label with all columns
            table_label = f"📊 {table_name}"
            
            # Add columns info
            if columns:
                pk_cols = [c['name'] for c in columns if c.get('is_primary_key')]
                fk_cols = [c['name'] for c in columns if c.get('is_foreign_key')]
                
                table_label += "\\n━━━━━━━━━━━━━━━━"
                
                # Show primary keys
                if pk_cols:
                    table_label += f"\\n🔑 PK: {', '.join(pk_cols)}"
                
                # Show foreign keys
                if fk_cols:
                    table_label += f"\\n🔗 FK: {', '.join(fk_cols)}"
                
                table_label += "\\n━━━━━━━━━━━━━━━━"
                
                # Show all columns (limit to 8 for readability)
                for col in columns[:8]:
                    col_name = col['name']
                    col_type = col.get('type', 'VARCHAR')
                    constraints = []
                    if col.get('is_primary_key'):
                        constraints.append('PK')
                    if col.get('is_foreign_key'):
                        constraints.append('FK')
                    if col.get('is_unique'):
                        constraints.append('U')
                    if col.get('is_not_null'):
                        constraints.append('NN')
                    
                    constraint_str = f" [{', '.join(constraints)}]" if constraints else ""
                    table_label += f"\\n• {col_name}: {col_type}{constraint_str}"
                
                if len(columns) > 8:
                    table_label += f"\\n... {len(columns) - 8} more columns"
            
            lines.append(f"    {root_id} --> {table_id}[\"{table_label}\"]")
            lines.append(f"    style {table_id} fill:#e3f2fd,stroke:#2196F3,stroke-width:2px")
        
        # Add foreign key relationships with labels
        for rel in relationships:
            from_table = rel.get('from_table')
            to_table = rel.get('to_table')
            from_column = rel.get('from_column')
            to_column = rel.get('to_column')
            
            if from_table in table_nodes and to_table in table_nodes:
                from_id = table_nodes[from_table]
                to_id = table_nodes[to_table]
                
                rel_label = f"{from_column} → {to_column}" if from_column and to_column else "FK"
                lines.append(f"    {from_id} -->|\"{rel_label}\"| {to_id}")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_combined_flowchart(self, funcs: List[Dict]) -> str:
        """Generate flowchart showing multiple functions."""
        lines = ["```mermaid", "flowchart TD"]
        
        # Create a node for each function
        for i, func in enumerate(funcs[:5]):  # Limit to 5 functions
            func_name = func['name']
            func_id = f"FUNC{i+1}"
            lines.append(f"    {func_id}([{func_name}])")
            
            # Show it has control flow
            func_flow = [cf for cf in self.control_flow if cf.get('function') == func_name]
            if func_flow:
                lines.append(f"    {func_id} --> FLOW{func_id}[Has {len(func_flow)} control structures]")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_structure_based_flowchart(self) -> str:
        """Generate flowchart based on code structure (classes, variables, imports) when no functions exist.
        
        Returns:
            Mermaid flowchart code as string
        """
        lines = ["```mermaid", "flowchart TD"]
        
        # Start node
        start_id = "Start"
        lines.append(f"    {start_id}([\"▶️ Code Structure\"])")
        lines.append(f"    style {start_id} fill:#e8f4f8,stroke:#2196F3,stroke-width:3px")
        
        # Add classes if available
        if self.classes:
            classes_id = "Classes"
            lines.append(f"    {start_id} --> {classes_id}[\"🏛️ Classes ({len(self.classes)})\"]")
            lines.append(f"    style {classes_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
            
            for i, cls in enumerate(self.classes[:5]):  # Limit to 5 classes
                cls_id = f"Class{i+1}"
                cls_name = cls.get('name', 'Unknown')
                methods_count = len(cls.get('methods', []))
                lines.append(f"    {classes_id} --> {cls_id}[\"📦 {cls_name}\"]")
                if methods_count > 0:
                    lines.append(f"    {cls_id} --> {cls_id}Methods[\"Methods: {methods_count}\"]")
                lines.append(f"    style {cls_id} fill:#e3f2fd,stroke:#2196F3")
        
        # Add variables if available
        global_vars = self.parse_result.get('global_variables', [])
        local_vars = self.parse_result.get('local_variables', [])
        if global_vars or local_vars:
            vars_id = "Variables"
            total_vars = len(global_vars) + len(local_vars)
            lines.append(f"    {start_id} --> {vars_id}[\"📊 Variables ({total_vars})\"]")
            lines.append(f"    style {vars_id} fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px")
            
            if global_vars:
                lines.append(f"    {vars_id} --> GlobalVars[\"Global: {len(global_vars)}\"]")
            if local_vars:
                lines.append(f"    {vars_id} --> LocalVars[\"Local: {len(local_vars)}\"]")
        
        # Add imports if available
        if self.imports:
            imports_id = "Imports"
            lines.append(f"    {start_id} --> {imports_id}[\"📦 Imports ({len(self.imports)})\"]")
            lines.append(f"    style {imports_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:2px")
            
            # Show first few imports
            for i, imp in enumerate(self.imports[:5]):
                imp_name = imp.get('module', imp.get('name', 'Unknown'))
                imp_id = f"Import{i+1}"
                lines.append(f"    {imports_id} --> {imp_id}[\"📥 {imp_name}\"]")
                lines.append(f"    style {imp_id} fill:#c8e6c9,stroke:#4caf50")
        
        # Add tables if available (for SQL or mixed projects)
        tables = self.parse_result.get('tables', [])
        if tables:
            tables_id = "Tables"
            lines.append(f"    {start_id} --> {tables_id}[\"🗄️ Tables ({len(tables)})\"]")
            lines.append(f"    style {tables_id} fill:#fff3e0,stroke:#ff9800,stroke-width:2px")
            
            for i, table in enumerate(tables[:5]):
                table_id = f"Table{i+1}"
                table_name = table.get('name', 'Unknown')
                cols_count = len(table.get('columns', []))
                lines.append(f"    {tables_id} --> {table_id}[\"📋 {table_name}\"]")
                lines.append(f"    {table_id} --> {table_id}Cols[\"Columns: {cols_count}\"]")
                lines.append(f"    style {table_id} fill:#ffe0b2,stroke:#ff9800")
        
        # If nothing found, show a helpful message
        if not self.classes and not global_vars and not local_vars and not self.imports and not tables:
            lines.append(f"    {start_id} --> Empty[\"📝 Empty or Unsupported Code\"]")
            lines.append(f"    Empty --> Note[\"Add functions, classes, or variables to see structure\"]")
            lines.append(f"    style Empty fill:#ffebee,stroke:#f44336")
            lines.append(f"    style Note fill:#fff4e6")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_structure_based_sequence(self) -> str:
        """Generate sequence diagram based on code structure when no function calls exist.
        
        Returns:
            Mermaid sequence diagram code as string
        """
        lines = ["```mermaid", "sequenceDiagram"]
        lines.append("    autonumber")
        
        # Add module as main participant
        lines.append('    participant Module as "📄 Module"')
        
        # Add classes as participants
        if self.classes:
            for i, cls in enumerate(self.classes[:6]):  # Limit to 6 classes
                cls_name = cls.get('name', 'Unknown')
                short_name = cls_name[:4].upper() if len(cls_name) > 4 else cls_name.upper()
                lines.append(f'    participant {short_name} as "🏛️ {cls_name}"')
                # Show class initialization
                lines.append(f'    Module->>{short_name}: Initialize')
        
        # Add top-level functions as participants
        top_level_funcs = [f for f in self.functions if not f.get('is_nested', False)]
        if top_level_funcs:
            for i, func in enumerate(top_level_funcs[:6]):  # Limit to 6 functions
                func_name = func.get('name', 'Unknown')
                short_name = func_name[:4].upper() if len(func_name) > 4 else func_name.upper()
                lines.append(f'    participant {short_name} as "⚙️ {func_name}"')
                lines.append(f'    Module->>{short_name}: Define')
        
        # Add imports as participants
        if self.imports:
            imports_group = []
            for imp in self.imports[:5]:  # Limit to 5 imports
                imp_name = imp.get('module', imp.get('name', 'Unknown'))
                imports_group.append(imp_name)
            if imports_group:
                lines.append(f'    participant Imports as "📦 Imports ({len(imports_group)})"')
                lines.append(f'    Module->>Imports: Import')
                for imp_name in imports_group:
                    lines.append(f'    Note over Imports: {imp_name}')
        
        # Add variables section
        global_vars = self.parse_result.get('global_variables', [])
        if global_vars:
            lines.append(f'    participant Vars as "📊 Variables ({len(global_vars)})"')
            lines.append(f'    Module->>Vars: Declare')
        
        # Add tables if available
        tables = self.parse_result.get('tables', [])
        if tables:
            lines.append(f'    participant Tables as "🗄️ Tables ({len(tables)})"')
            lines.append(f'    Module->>Tables: Define Schema')
        
        # If nothing found, show a helpful message
        if not self.classes and not top_level_funcs and not self.imports and not global_vars and not tables:
            lines.append('    Note over Module: No code structure detected')
            lines.append('    Note over Module: Add classes, functions, or imports to see interactions')
        
        lines.append("```")
        return "\n".join(lines)

