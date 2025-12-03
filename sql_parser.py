"""
SQL code parser to extract tables, columns, and relationships.
"""

import re
from typing import Dict, List, Any, Set, Tuple


class SQLParser:
    """Parse SQL code to extract tables and relationships."""
    
    def __init__(self):
        self.tables = []
        self.relationships = []
        # Add empty lists to match Python parser structure
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
        self.import_usage = []
    
    def parse(self, code: str) -> Dict[str, Any]:
        """Parse SQL code and extract table structure.
        
        Args:
            code: SQL source code
            
        Returns:
            Dictionary with parsed structure
        """
        # Reset state
        self.tables = []
        self.relationships = []
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
        self.import_usage = []
        
        # Store original code for line counting
        self.original_code = code
        
        # Normalize SQL (remove comments, normalize whitespace)
        normalized_code = self._normalize_sql(code)
        
        # Extract CREATE TABLE statements
        self._extract_tables(normalized_code, code)
        
        # Extract relationships (foreign keys, joins)
        self._extract_relationships(normalized_code, code)
        
        # Count methods (empty for SQL)
        methods = []
        for cls in self.classes:
            methods.extend(cls.get('methods', []))
        
        # Count variables (empty for SQL)
        class_vars = []
        instance_vars = []
        for cls in self.classes:
            class_vars.extend(cls.get('class_variables', []))
            instance_vars.extend(cls.get('instance_variables', []))
        
        return {
            'summary': {
                'total_functions': len(self.functions),
                'sync_functions': len([f for f in self.functions if not f.get('is_async', False) and not f.get('is_nested', False)]),
                'async_functions': len([f for f in self.functions if f.get('is_async', False) and not f.get('is_nested', False)]),
                'nested_functions': len([f for f in self.functions if f.get('is_nested', False)]),
                'total_classes': len(self.classes),
                'total_methods': len(methods),
                'global_variables': len(self.global_vars),
                'local_variables': len(self.local_vars),
                'execution_scope_variables': len(self.execution_scope_vars),
                'class_variables': len(class_vars),
                'instance_variables': len(instance_vars),
                'total_decorators': len(self.decorators),
                'total_imports': len(self.imports),
                'total_tables': len(self.tables),
                'total_relationships': len(self.relationships)
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
            'tables': self.tables,
            'relationships': self.relationships,
            'language': 'sql'
        }
    
    def _normalize_sql(self, code: str) -> str:
        """Normalize SQL code for easier parsing.
        
        Preserves line structure for better pattern matching.
        """
        # Remove single-line comments
        code = re.sub(r'--.*$', '', code, flags=re.MULTILINE)
        # Remove multi-line comments
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        # Normalize whitespace but preserve newlines for CREATE TABLE boundaries
        # Replace multiple spaces/tabs with single space, but keep newlines
        lines = code.split('\n')
        normalized_lines = []
        for line in lines:
            # Normalize whitespace on each line
            normalized_line = re.sub(r'[ \t]+', ' ', line.strip())
            if normalized_line:  # Keep non-empty lines
                normalized_lines.append(normalized_line)
        # Join with spaces (we'll use DOTALL in patterns anyway)
        return ' '.join(normalized_lines)
    
    def _extract_tables(self, normalized_code: str, original_code: str):
        """Extract CREATE TABLE statements.
        
        Args:
            normalized_code: Normalized SQL code for pattern matching
            original_code: Original SQL code for line counting
        """
        # Pattern to find CREATE TABLE statements
        create_table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)'
        
        for match in re.finditer(create_table_pattern, normalized_code, re.IGNORECASE):
            table_name = match.group(1)
            start_pos = match.end()
            
            # Find the opening parenthesis
            paren_pos = normalized_code.find('(', start_pos)
            if paren_pos == -1:
                continue
            
            # Find matching closing parenthesis
            depth = 0
            end_pos = paren_pos
            for i in range(paren_pos, len(normalized_code)):
                if normalized_code[i] == '(':
                    depth += 1
                elif normalized_code[i] == ')':
                    depth -= 1
                    if depth == 0:
                        end_pos = i
                        break
            
            if depth != 0:
                # Unmatched parentheses, skip this table
                continue
            
            # Extract columns string (between parentheses)
            columns_str = normalized_code[paren_pos + 1:end_pos]
            
            # Extract columns
            columns = []
            # Split by comma, but be careful with nested parentheses
            column_defs = self._split_column_definitions(columns_str)
            
            for col_def in column_defs:
                col_def = col_def.strip()
                if not col_def:
                    continue
                
                # Extract column name (first word)
                col_match = re.match(r'(\w+)', col_def)
                if col_match:
                    col_name = col_match.group(1)
                    
                    # Extract data type - get the full type including size
                    type_match = re.search(r'(\w+(?:\([^)]*\))?)', col_def)
                    col_type = type_match.group(1) if type_match else 'unknown'
                    
                    # Check for constraints
                    is_primary_key = 'PRIMARY KEY' in col_def.upper()
                    is_foreign_key = 'FOREIGN KEY' in col_def.upper() or 'REFERENCES' in col_def.upper()
                    is_unique = 'UNIQUE' in col_def.upper()
                    is_not_null = 'NOT NULL' in col_def.upper()
                    
                    columns.append({
                        'name': col_name,
                        'type': col_type,
                        'is_primary_key': is_primary_key,
                        'is_foreign_key': is_foreign_key,
                        'is_unique': is_unique,
                        'is_not_null': is_not_null
                    })
            
            # Find the line number in original code by searching for the table name
            # Search for "CREATE TABLE table_name" in original code
            table_pattern = re.compile(rf'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(table_name)}', re.IGNORECASE)
            original_match = table_pattern.search(original_code)
            line_num = original_code[:original_match.start()].count('\n') + 1 if original_match else 1
            
            self.tables.append({
                'name': table_name,
                'columns': columns,
                'line': line_num
            })
    
    def _split_column_definitions(self, columns_str: str) -> List[str]:
        """Split column definitions, handling nested parentheses."""
        result = []
        current = ''
        depth = 0
        
        for char in columns_str:
            if char == '(':
                depth += 1
                current += char
            elif char == ')':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                if current.strip():
                    result.append(current.strip())
                current = ''
            else:
                current += char
        
        if current.strip():
            result.append(current.strip())
        
        return result
    
    def _extract_relationships(self, normalized_code: str, original_code: str):
        """Extract foreign key relationships.
        
        Args:
            normalized_code: Normalized SQL code for pattern matching
            original_code: Original SQL code for finding table positions
        """
        # First, extract all table names and their positions from original code
        table_positions = {}
        for match in re.finditer(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)', original_code, re.IGNORECASE):
            table_name = match.group(1)
            table_positions[match.start()] = table_name
        
        # Pattern for FOREIGN KEY references
        fk_pattern = r'FOREIGN\s+KEY\s*\((\w+)\)\s+REFERENCES\s+(\w+)\s*\((\w+)\)'
        
        for match in re.finditer(fk_pattern, normalized_code, re.IGNORECASE):
            from_column = match.group(1)
            to_table = match.group(2)
            to_column = match.group(3)
            
            # Find which table this FK belongs to - search in original code
            # Find the position in original code by searching for the FK pattern
            fk_search_pattern = re.compile(rf'FOREIGN\s+KEY\s*\(\s*{re.escape(from_column)}\s*\)\s+REFERENCES\s+{re.escape(to_table)}', re.IGNORECASE)
            original_fk_match = fk_search_pattern.search(original_code)
            
            if original_fk_match:
                before_pos = original_fk_match.start()
                from_table = None
                for pos in sorted(table_positions.keys(), reverse=True):
                    if pos < before_pos:
                        from_table = table_positions[pos]
                        break
            else:
                from_table = None
            
            if from_table:
                self.relationships.append({
                    'from_table': from_table,
                    'from_column': from_column,
                    'to_table': to_table,
                    'to_column': to_column,
                    'type': 'foreign_key'
                })
        
        # Also check for REFERENCES in column definitions (inline FK)
        ref_pattern = r'(\w+)\s+\w+[^,)]*?REFERENCES\s+(\w+)\s*\((\w+)\)'
        for match in re.finditer(ref_pattern, normalized_code, re.IGNORECASE):
            from_column = match.group(1)
            to_table = match.group(2)
            to_column = match.group(3)
            
            # Find position in original code
            ref_search_pattern = re.compile(rf'{re.escape(from_column)}\s+\w+[^,)]*?REFERENCES\s+{re.escape(to_table)}', re.IGNORECASE)
            original_ref_match = ref_search_pattern.search(original_code)
            
            if original_ref_match:
                before_pos = original_ref_match.start()
                from_table = None
                for pos in sorted(table_positions.keys(), reverse=True):
                    if pos < before_pos:
                        from_table = table_positions[pos]
                        break
            else:
                from_table = None
            
            if from_table:
                # Avoid duplicates
                if not any(r['from_table'] == from_table and r['from_column'] == from_column 
                          for r in self.relationships):
                    self.relationships.append({
                        'from_table': from_table,
                        'from_column': from_column,
                        'to_table': to_table,
                        'to_column': to_column,
                        'type': 'foreign_key'
                    })

