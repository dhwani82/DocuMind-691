import os
import re
from typing import Dict, List, Any, Optional
import json

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class DocumentationGenerator:
    """Generate professional documentation using LLM or template-based approach."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the documentation generator.
        
        Args:
            api_key: OpenAI API key. If None, uses template-based generation.
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.client = None
        
        if OPENAI_AVAILABLE and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                self.use_llm = True
            except Exception:
                self.use_llm = False
        else:
            self.use_llm = False
    
    def generate_documentation(self, code: str, parse_result: Dict[str, Any]) -> Dict[str, str]:
        """Generate comprehensive documentation for the parsed code.
        
        Args:
            code: Original source code
            parse_result: Result from CodeParser.parse()
            
        Returns:
            Dictionary with 'docstrings', 'readme', and 'architecture' keys
        """
        if self.use_llm:
            return self._generate_with_llm(code, parse_result)
        else:
            return self._generate_with_templates(code, parse_result)
    
    def _generate_with_llm(self, code: str, parse_result: Dict[str, Any]) -> Dict[str, str]:
        """Generate documentation using LLM."""
        try:
            # Generate docstrings
            docstrings = self._generate_docstrings_llm(code, parse_result)
            
            # Generate README
            readme = self._generate_readme_llm(code, parse_result)
            
            # Generate ARCHITECTURE
            architecture = self._generate_architecture_llm(code, parse_result)
            
            return {
                'docstrings': docstrings,
                'readme': readme,
                'architecture': architecture
            }
        except Exception as e:
            # Fallback to templates if LLM fails
            return self._generate_with_templates(code, parse_result)
    
    def _generate_docstrings_llm(self, code: str, parse_result: Dict[str, Any]) -> str:
        """Generate PEP 257 compliant docstrings using LLM."""
        prompt = f"""You are a Python documentation expert. Generate professional docstrings following PEP 257 conventions for the following code.

Requirements:
1. Use triple-quoted strings (three double quotes)
2. First line should be a brief summary (imperative mood)
3. Add detailed description if needed
4. Document parameters with Args: section
5. Document return values with Returns: section
6. Document exceptions with Raises: section if applicable
7. Use proper formatting and indentation
8. Be concise but comprehensive

Code to document:
```python
{code}
```

Parse information:
{json.dumps(parse_result, indent=2)}

Generate the complete code with professional docstrings added. Return ONLY the code with docstrings, no explanations."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a Python documentation expert specializing in PEP 257 compliant docstrings."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    
    def _generate_readme_llm(self, code: str, parse_result: Dict[str, Any]) -> str:
        """Generate README.md using LLM."""
        summary = parse_result['summary']
        
        prompt = f"""Generate a professional README.md file for this Python project based on the code analysis.

Code structure:
- {summary['total_functions']} functions ({summary['sync_functions']} sync, {summary['async_functions']} async)
- {summary['total_classes']} classes
- {summary['total_methods']} methods
- {summary['total_imports']} imports

Code preview (first 500 chars):
{code[:500]}

Create a README.md that includes:
1. Project title and description
2. Features
3. Installation instructions
4. Usage examples
5. Function/class overview
6. Requirements/dependencies
7. License section (if applicable)

Format it as clean, professional Markdown. Be specific about what the code does based on the structure."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a technical writer specializing in software documentation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )
        
        return response.choices[0].message.content.strip()
    
    def _generate_architecture_llm(self, code: str, parse_result: Dict[str, Any]) -> str:
        """Generate ARCHITECTURE.md using LLM."""
        classes = parse_result.get('classes', [])
        functions = parse_result.get('functions', [])
        imports = parse_result.get('imports', [])
        
        prompt = f"""Generate a professional ARCHITECTURE.md document explaining the code structure and module relationships.

Classes:
{json.dumps(classes, indent=2)}

Functions:
{json.dumps(functions[:10], indent=2)}  # First 10 functions

Imports:
{json.dumps(imports, indent=2)}

Code preview:
{code[:800]}

Create an ARCHITECTURE.md that includes:
1. Overview of the system
2. Module structure
3. Class hierarchy and relationships
4. Function organization
5. Data flow (if applicable)
6. Dependencies and external libraries
7. Design patterns used (if any)

Format as clean, professional Markdown with clear sections and subsections."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a software architect documenting system design."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )
        
        return response.choices[0].message.content.strip()
    
    def _generate_with_templates(self, code: str, parse_result: Dict[str, Any]) -> Dict[str, str]:
        """Generate documentation using templates (fallback when LLM unavailable)."""
        docstrings = self._generate_docstrings_template(code, parse_result)
        readme = self._generate_readme_template(parse_result)
        architecture = self._generate_architecture_template(parse_result)
        
        return {
            'docstrings': docstrings,
            'readme': readme,
            'architecture': architecture
        }
    
    def _generate_docstrings_template(self, code: str, parse_result: Dict[str, Any]) -> str:
        """Generate docstrings using template-based approach."""
        lines = code.split('\n')
        result_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            result_lines.append(line)
            
            # Check if this is a function or class definition
            stripped = line.strip()
            
            # Function definition
            if stripped.startswith('def ') or stripped.startswith('async def '):
                indent = len(line) - len(line.lstrip())
                func_name = self._extract_name(stripped)
                
                # Find function info
                func_info = self._find_function_info(func_name, parse_result)
                
                if func_info and not self._has_docstring(lines, i):
                    docstring = self._create_function_docstring(func_info, indent + 4)
                    result_lines.append(docstring)
            
            # Class definition
            elif stripped.startswith('class '):
                indent = len(line) - len(line.lstrip())
                class_name = self._extract_class_name(stripped)
                
                class_info = self._find_class_info(class_name, parse_result)
                
                if class_info and not self._has_docstring(lines, i):
                    docstring = self._create_class_docstring(class_info, indent + 4)
                    result_lines.append(docstring)
            
            i += 1
        
        return '\n'.join(result_lines)
    
    def _generate_readme_template(self, parse_result: Dict[str, Any]) -> str:
        """Generate README.md using template."""
        summary = parse_result['summary']
        functions = parse_result.get('functions', [])
        classes = parse_result.get('classes', [])
        imports = parse_result.get('imports', [])
        
        # Extract dependencies
        dependencies = []
        for imp in imports:
            if imp['type'] == 'import':
                dependencies.append(imp['module'].split('.')[0])
            elif imp['type'] == 'from_import' and imp['module']:
                dependencies.append(imp['module'].split('.')[0])
        dependencies = sorted(set(dependencies))
        
        readme = f"""# Project Documentation

## Overview

This project contains {summary['total_functions']} functions and {summary['total_classes']} classes.

## Features

- {summary['sync_functions']} synchronous functions
- {summary['async_functions']} asynchronous functions
- {summary['total_classes']} classes with {summary['total_methods']} methods
- {summary['global_variables']} global variables
- {summary['class_variables']} class variables
- {summary['instance_variables']} instance variables

## Installation

```bash
pip install {' '.join(dependencies) if dependencies else 'No external dependencies'}
```

## Usage

### Functions

"""
        
        for func in functions[:10]:  # First 10 functions
            readme += f"#### `{func['name']}`\n\n"
            readme += f"- **Type**: {'Async' if func.get('is_async') else 'Sync'}\n"
            readme += f"- **Parameters**: {', '.join(func.get('parameters', []))}\n"
            if func.get('returns'):
                readme += f"- **Returns**: {func['returns']}\n"
            readme += "\n"
        
        readme += "\n### Classes\n\n"
        
        for cls in classes:
            readme += f"#### `{cls['name']}`\n\n"
            if cls.get('bases'):
                readme += f"- **Inherits from**: {', '.join(cls['bases'])}\n"
            readme += f"- **Methods**: {len(cls.get('methods', []))}\n"
            readme += f"- **Class variables**: {len(cls.get('class_variables', []))}\n"
            readme += f"- **Instance variables**: {len(cls.get('instance_variables', []))}\n"
            readme += "\n"
        
        readme += """## Structure

This project follows standard Python conventions and includes proper type hints and documentation.

## License

[Add your license here]
"""
        
        return readme
    
    def _generate_architecture_template(self, parse_result: Dict[str, Any]) -> str:
        """Generate ARCHITECTURE.md using template."""
        classes = parse_result.get('classes', [])
        functions = parse_result.get('functions', [])
        imports = parse_result.get('imports', [])
        
        arch = """# Architecture Documentation

## Overview

This document describes the architecture and structure of the codebase.

## Module Structure

"""
        
        # Dependencies
        arch += "### Dependencies\n\n"
        for imp in imports:
            if imp['type'] == 'import':
                arch += f"- `{imp['module']}`\n"
            elif imp['type'] == 'from_import':
                arch += f"- `{imp['module']}.{imp['name']}`\n"
        
        arch += "\n### Classes\n\n"
        
        for cls in classes:
            arch += f"#### {cls['name']}\n\n"
            if cls.get('bases'):
                arch += f"**Inheritance**: Extends {', '.join(cls['bases'])}\n\n"
            arch += f"**Methods**: {len(cls.get('methods', []))}\n\n"
            if cls.get('methods'):
                arch += "Methods:\n"
                for method in cls['methods']:
                    arch += f"- `{method['name']}` ({'async' if method.get('is_async') else 'sync'})\n"
            arch += "\n"
        
        arch += "### Functions\n\n"
        
        top_level_funcs = [f for f in functions if not f.get('is_nested')]
        arch += f"Total top-level functions: {len(top_level_funcs)}\n\n"
        
        for func in top_level_funcs[:10]:
            arch += f"- `{func['name']}` ({'async' if func.get('is_async') else 'sync'})\n"
        
        arch += "\n## Relationships\n\n"
        
        # Class hierarchy
        if classes:
            arch += "### Class Hierarchy\n\n"
            for cls in classes:
                if cls.get('bases'):
                    arch += f"- `{cls['name']}` → {', '.join(cls['bases'])}\n"
        
        arch += "\n## Design Patterns\n\n"
        arch += "[Document any design patterns used in the codebase]\n"
        
        return arch
    
    def _extract_name(self, line: str) -> str:
        """Extract function name from definition line."""
        match = re.match(r'(?:async\s+)?def\s+(\w+)', line)
        return match.group(1) if match else ""
    
    def _extract_class_name(self, line: str) -> str:
        """Extract class name from definition line."""
        match = re.match(r'class\s+(\w+)', line)
        return match.group(1) if match else ""
    
    def _find_function_info(self, name: str, parse_result: Dict[str, Any]) -> Optional[Dict]:
        """Find function information in parse result."""
        for func in parse_result.get('functions', []):
            if func['name'] == name:
                return func
        return None
    
    def _find_class_info(self, name: str, parse_result: Dict[str, Any]) -> Optional[Dict]:
        """Find class information in parse result."""
        for cls in parse_result.get('classes', []):
            if cls['name'] == name:
                return cls
        return None
    
    def _has_docstring(self, lines: List[str], def_line: int) -> bool:
        """Check if function/class already has a docstring."""
        if def_line + 1 >= len(lines):
            return False
        
        next_line = lines[def_line + 1].strip()
        return next_line.startswith('"""') or next_line.startswith("'''")
    
    def _create_function_docstring(self, func_info: Dict, indent: int) -> str:
        """Create PEP 257 compliant docstring for function."""
        indent_str = ' ' * indent
        docstring = f'{indent_str}"""'
        
        # Summary
        docstring += f"{func_info['name'].replace('_', ' ').title()}."
        
        # Parameters
        params = func_info.get('parameters', [])
        if params:
            docstring += "\n\n"
            docstring += f"{indent_str}Args:\n"
            for param in params:
                if param != 'self':
                    docstring += f"{indent_str}    {param}: Description of {param}.\n"
        
        # Returns
        if func_info.get('returns'):
            docstring += f"\n{indent_str}Returns:\n"
            docstring += f"{indent_str}    {func_info['returns']}: Description of return value.\n"
        
        docstring += f'{indent_str}"""'
        return docstring
    
    def _create_class_docstring(self, class_info: Dict, indent: int) -> str:
        """Create PEP 257 compliant docstring for class."""
        indent_str = ' ' * indent
        docstring = f'{indent_str}"""'
        
        # Summary
        docstring += f"{class_info['name'].replace('_', ' ').title()}."
        
        # Inheritance
        if class_info.get('bases'):
            docstring += f"\n\n{indent_str}Inherits from: {', '.join(class_info['bases'])}."
        
        # Methods overview
        methods = class_info.get('methods', [])
        if methods:
            docstring += f"\n\n{indent_str}Methods:\n"
            for method in methods[:5]:  # First 5 methods
                docstring += f"{indent_str}    {method['name']}: Description.\n"
        
        docstring += f'{indent_str}"""'
        return docstring

