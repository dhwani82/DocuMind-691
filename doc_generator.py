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
        self.use_llm = False
        
        if OPENAI_AVAILABLE and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                self.use_llm = True
            except Exception:
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
                    docstring = self._create_function_docstring(func_info, indent + 4, parse_result)
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
    
    def generate_project_documentation(self, project_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate comprehensive documentation for a project.
        
        Args:
            project_data: Project data from scan_project() containing:
                - summary: Aggregated statistics
                - file_details: List of parsed file information
                - functions: All functions from all files
                - classes: All classes from all files
                - tables: All SQL tables (if any)
                - github_repo_url: GitHub URL (if applicable)
                - cloned_path: Local clone path (if applicable)
                
        Returns:
            Dictionary with 'docstrings', 'readme', and 'architecture' keys
        """
        if self.use_llm:
            return self._generate_project_docs_with_llm(project_data)
        else:
            return self._generate_project_docs_with_templates(project_data)
    
    def _generate_project_docs_with_llm(self, project_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate project documentation using LLM."""
        try:
            # Generate README
            readme = self._generate_project_readme_llm(project_data)
            
            # Generate ARCHITECTURE
            architecture = self._generate_project_architecture_llm(project_data)
            
            # Generate docstrings summary (for all files)
            docstrings = self._generate_project_docstrings_llm(project_data)
            
            return {
                'docstrings': docstrings,
                'readme': readme,
                'architecture': architecture
            }
        except Exception as e:
            # Fallback to templates if LLM fails
            return self._generate_project_docs_with_templates(project_data)
    
    def _generate_project_readme_llm(self, project_data: Dict[str, Any]) -> str:
        """Generate README.md for project using LLM."""
        summary = project_data.get('summary', {})
        file_details = project_data.get('file_details', [])
        functions = project_data.get('functions', [])
        classes = project_data.get('classes', [])
        github_repo_url = project_data.get('github_repo_url', '')
        detected_languages = project_data.get('detected_languages', [])
        
        # Build file structure overview
        file_structure = "\n".join([
            f"- {fd.get('path', 'unknown')} ({fd.get('language', 'unknown')}) - {fd.get('functions_count', 0)} functions, {fd.get('classes_count', 0)} classes"
            for fd in file_details[:20]  # First 20 files
        ])
        if len(file_details) > 20:
            file_structure += f"\n... and {len(file_details) - 20} more files"
        
        prompt = f"""Generate a professional README.md file for this project based on the analysis.

Project Statistics:
- Total Files: {summary.get('total_files', 0)}
- Total Lines: {summary.get('total_lines', 0)}
- Total Functions: {summary.get('total_functions', 0)} ({summary.get('sync_functions', 0)} sync, {summary.get('async_functions', 0)} async)
- Total Classes: {summary.get('total_classes', 0)} with {summary.get('total_methods', 0)} methods
- Total Tables: {summary.get('total_tables', 0)} (SQL)
- Languages: {', '.join(detected_languages) if detected_languages else 'Mixed'}

{f'GitHub Repository: {github_repo_url}' if github_repo_url else ''}

File Structure (sample):
{file_structure}

Key Functions (sample):
{chr(10).join([f"- {f.get('name', 'unknown')} (line {f.get('line', 'N/A')})" for f in functions[:15]])}

Key Classes (sample):
{chr(10).join([f"- {c.get('name', 'unknown')} (line {c.get('line', 'N/A')})" for c in classes[:10]])}

Create a comprehensive README.md that includes:
1. Project title and description
2. Features overview
3. Installation instructions
4. Usage examples
5. Project structure
6. Key components (functions, classes, modules)
7. Requirements/dependencies
8. Contributing guidelines (if applicable)
9. License section (if applicable)

Format it as clean, professional Markdown. Be specific about what the project does based on the structure and statistics."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a technical writer specializing in software documentation for multi-file projects."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    
    def _generate_project_architecture_llm(self, project_data: Dict[str, Any]) -> str:
        """Generate ARCHITECTURE.md for project using LLM."""
        summary = project_data.get('summary', {})
        file_details = project_data.get('file_details', [])
        functions = project_data.get('functions', [])
        classes = project_data.get('classes', [])
        tables = project_data.get('tables', [])
        imports = project_data.get('imports', [])
        detected_languages = project_data.get('detected_languages', [])
        
        # Build dependency graph
        dependencies = set()
        for imp in imports:
            if imp.get('module'):
                dependencies.add(imp['module'].split('.')[0])
        
        prompt = f"""Generate a comprehensive ARCHITECTURE.md document for this project.

Project Overview:
- Total Files: {summary.get('total_files', 0)}
- Total Lines: {summary.get('total_lines', 0)}
- Languages: {', '.join(detected_languages) if detected_languages else 'Mixed'}
- Total Functions: {summary.get('total_functions', 0)}
- Total Classes: {summary.get('total_classes', 0)}
- Total Tables: {summary.get('total_tables', 0)}

Key Dependencies:
{', '.join(sorted(dependencies)[:20])}

File Structure:
{chr(10).join([f"- {fd.get('path', 'unknown')}: {fd.get('language', 'unknown')} ({fd.get('functions_count', 0)} functions, {fd.get('classes_count', 0)} classes)" for fd in file_details[:15]])}

Create a detailed architecture document that includes:
1. System Overview
2. Architecture Patterns
3. Component Structure
4. Data Flow
5. Key Modules and Their Responsibilities
6. Dependencies and External Libraries
7. Database Schema (if applicable)
8. API Structure (if applicable)
9. Design Decisions
10. Future Improvements

Format it as professional Markdown documentation."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a software architect specializing in system design documentation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    
    def _generate_project_docstrings_llm(self, project_data: Dict[str, Any]) -> str:
        """Generate docstrings summary for project using LLM."""
        summary = project_data.get('summary', {})
        functions = project_data.get('functions', [])
        classes = project_data.get('classes', [])
        
        prompt = f"""Generate a comprehensive documentation summary for this project's codebase.

Project Statistics:
- Total Functions: {summary.get('total_functions', 0)}
- Total Classes: {summary.get('total_classes', 0)}
- Total Methods: {summary.get('total_methods', 0)}

Key Functions:
{chr(10).join([f"- {f.get('name', 'unknown')} (line {f.get('line', 'N/A')}, file: {f.get('file', 'unknown')})" for f in functions[:30]])}

Key Classes:
{chr(10).join([f"- {c.get('name', 'unknown')} (line {c.get('line', 'N/A')}, file: {c.get('file', 'unknown')})" for c in classes[:20]])}

Create a comprehensive documentation guide that includes:
1. Overview of all major functions and their purposes
2. Class hierarchy and relationships
3. Function signatures and parameters
4. Return types and behaviors
5. Usage examples for key functions
6. Best practices for using this codebase

Format it as professional documentation in Markdown."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a documentation expert specializing in API and codebase documentation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    
    def _generate_project_docs_with_templates(self, project_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate project documentation using templates."""
        summary = project_data.get('summary', {})
        file_details = project_data.get('file_details', [])
        functions = project_data.get('functions', [])
        classes = project_data.get('classes', [])
        tables = project_data.get('tables', [])
        imports = project_data.get('imports', [])
        github_repo_url = project_data.get('github_repo_url', '')
        detected_languages = project_data.get('detected_languages', [])
        
        # Extract dependencies
        dependencies = set()
        for imp in imports:
            if imp.get('module'):
                dependencies.add(imp['module'].split('.')[0])
        
        # Generate README
        readme = f"""# Project Documentation

## Overview

This project contains {summary.get('total_files', 0)} files with {summary.get('total_lines', 0)} lines of code.

{f'**GitHub Repository**: [{github_repo_url}]({github_repo_url})' if github_repo_url else ''}

## Statistics

- **Total Files**: {summary.get('total_files', 0)}
- **Total Lines**: {summary.get('total_lines', 0):,}
- **Total Functions**: {summary.get('total_functions', 0)} ({summary.get('sync_functions', 0)} sync, {summary.get('async_functions', 0)} async)
- **Total Classes**: {summary.get('total_classes', 0)} with {summary.get('total_methods', 0)} methods
- **Total Tables**: {summary.get('total_tables', 0)}
- **Languages**: {', '.join(detected_languages) if detected_languages else 'Mixed'}

## Project Structure

"""
        
        for file_detail in file_details[:30]:  # First 30 files
            path = file_detail.get('path', 'unknown')
            lang = file_detail.get('language', 'unknown')
            func_count = file_detail.get('functions_count', 0)
            class_count = file_detail.get('classes_count', 0)
            readme += f"- `{path}` ({lang}) - {func_count} functions, {class_count} classes\n"
        
        if len(file_details) > 30:
            readme += f"\n... and {len(file_details) - 30} more files\n"
        
        readme += f"""
## Installation

```bash
pip install {' '.join(sorted(dependencies)[:20]) if dependencies else '# No external dependencies detected'}
```

## Key Components

### Functions

"""
        
        for func in functions[:20]:  # First 20 functions
            name = func.get('name', 'unknown')
            line = func.get('line', 'N/A')
            file_path = func.get('file', 'unknown')
            readme += f"- **{name}** (line {line}, `{file_path}`)\n"
        
        readme += "\n### Classes\n\n"
        
        for cls in classes[:15]:  # First 15 classes
            name = cls.get('name', 'unknown')
            line = cls.get('line', 'N/A')
            file_path = cls.get('file', 'unknown')
            methods = cls.get('methods', [])
            readme += f"- **{name}** (line {line}, `{file_path}`) - {len(methods)} methods\n"
        
        # Generate Architecture
        architecture = f"""# Architecture Documentation

## System Overview

This project is a {', '.join(detected_languages) if detected_languages else 'multi-language'} codebase with {summary.get('total_files', 0)} files.

## Component Structure

### Files by Language

"""
        
        # Group files by language
        files_by_lang = {}
        for fd in file_details:
            lang = fd.get('language', 'unknown')
            if lang not in files_by_lang:
                files_by_lang[lang] = []
            files_by_lang[lang].append(fd)
        
        for lang, files in files_by_lang.items():
            architecture += f"\n#### {lang.upper()}\n\n"
            for fd in files[:10]:
                architecture += f"- `{fd.get('path', 'unknown')}`\n"
            if len(files) > 10:
                architecture += f"- ... and {len(files) - 10} more {lang} files\n"
        
        architecture += f"""
## Dependencies

{', '.join(sorted(dependencies)[:30]) if dependencies else 'No external dependencies detected'}

## Database Schema

"""
        
        if tables:
            for table in tables[:10]:
                name = table.get('name', 'unknown')
                columns = table.get('columns', [])
                architecture += f"\n### {name}\n\n"
                for col in columns[:10]:
                    col_name = col.get('name', 'unknown')
                    col_type = col.get('type', 'unknown')
                    is_pk = ' (PRIMARY KEY)' if col.get('is_primary_key') else ''
                    architecture += f"- `{col_name}`: {col_type}{is_pk}\n"
        else:
            architecture += "No database tables found.\n"
        
        # Generate docstrings summary
        docstrings = f"""# Code Documentation Summary

## Functions

"""
        
        for func in functions[:30]:
            name = func.get('name', 'unknown')
            params = func.get('parameters', [])
            file_path = func.get('file', 'unknown')
            line = func.get('line', 'N/A')
            docstrings += f"\n### {name}\n\n"
            docstrings += f"- **File**: `{file_path}` (line {line})\n"
            docstrings += f"- **Parameters**: {', '.join([p.get('name', p) if isinstance(p, dict) else str(p) for p in params]) if params else 'None'}\n"
        
        docstrings += "\n## Classes\n\n"
        
        for cls in classes[:20]:
            name = cls.get('name', 'unknown')
            methods = cls.get('methods', [])
            file_path = cls.get('file', 'unknown')
            line = cls.get('line', 'N/A')
            docstrings += f"\n### {name}\n\n"
            docstrings += f"- **File**: `{file_path}` (line {line})\n"
            docstrings += f"- **Methods**: {len(methods)}\n"
            for method in methods[:5]:
                method_name = method.get('name', 'unknown')
                docstrings += f"  - `{method_name}`\n"
        
        return {
            'docstrings': docstrings,
            'readme': readme,
            'architecture': architecture
        }
    
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
    
    def _create_function_docstring(self, func_info: Dict, indent: int, parse_result: Dict[str, Any] = None) -> str:
        """Create PEP 257 compliant docstring for function with detailed explanations."""
        indent_str = ' ' * indent
        docstring = f'{indent_str}"""'
        
        func_name = func_info['name']
        
        # Analyze function behavior from control flow and calls
        description = self._analyze_function_behavior(func_info, parse_result)
        
        # Summary - use analyzed description or generate from name
        if description:
            # Split description into main description and exception handling if needed
            if "Handles" in description:
                # Split at "Handles" to separate main description from exception info
                parts = description.split("Handles", 1)
                main_desc = parts[0].strip().rstrip(',').rstrip('.').rstrip('and').strip()
                if len(parts) > 1:
                    exception_desc = "Handles " + parts[1].strip().rstrip('.')
                    docstring += f"\n{indent_str}{main_desc}."
                    docstring += f"\n{indent_str}{exception_desc}."
                else:
                    docstring += f"\n{indent_str}{description}"
            else:
                # Remove trailing period if already present
                clean_desc = description.rstrip('.')
                docstring += f"\n{indent_str}{clean_desc}."
        else:
            # Generate from function name with better descriptions
            name_words = func_name.replace('_', ' ').split()
            func_name_lower = func_name.lower()
            
            # Check function name patterns for common operations
            if func_name_lower == 'add':
                docstring += f"\n{indent_str}Returns the sum of two numbers."
            elif func_name_lower in ['subtract', 'sub']:
                docstring += f"\n{indent_str}Returns the difference of two numbers."
            elif func_name_lower in ['multiply', 'mul']:
                docstring += f"\n{indent_str}Returns the product of two numbers."
            elif func_name_lower in ['divide', 'div']:
                docstring += f"\n{indent_str}Returns the quotient of two numbers."
            elif len(name_words) > 1:
                action = name_words[0].lower()
                if action in ['get', 'fetch', 'retrieve', 'obtain', 'take']:
                    docstring += f"\n{indent_str}Retrieves {name_words[1]}."
                elif action in ['set', 'update', 'modify', 'change']:
                    docstring += f"\n{indent_str}Sets or updates {name_words[1]}."
                elif action in ['create', 'make', 'build', 'generate']:
                    docstring += f"\n{indent_str}Creates {name_words[1]}."
                elif action in ['process', 'handle', 'execute', 'run']:
                    docstring += f"\n{indent_str}Processes {name_words[1]}."
                else:
                    docstring += f"\n{indent_str}{func_name.replace('_', ' ').title()}."
            else:
                docstring += f"\n{indent_str}{func_name.replace('_', ' ').title()}."
        
        # Parameters
        params = func_info.get('parameters', [])
        if params:
            docstring += "\n\n"
            docstring += f"{indent_str}Args:\n"
            for param in params:
                if param != 'self':
                    # Generate better parameter descriptions
                    param_desc = self._generate_parameter_description(param, func_info, parse_result)
                    docstring += f"{indent_str}    {param}: {param_desc}\n"
        
        # Returns
        returns_info = self._analyze_return_behavior(func_info, parse_result)
        if returns_info:
            docstring += f"\n{indent_str}Returns:\n"
            docstring += f"{indent_str}    {returns_info}\n"
        elif func_info.get('returns'):
            docstring += f"\n{indent_str}Returns:\n"
            docstring += f"{indent_str}    {func_info['returns']}: Description of return value.\n"
        
        # Raises section for exception handling
        raises_info = self._analyze_exceptions(func_info, parse_result)
        if raises_info:
            docstring += f"\n{indent_str}Raises:\n"
            for exc_info in raises_info:
                docstring += f"{indent_str}    {exc_info}\n"
        
        docstring += f'{indent_str}"""'
        return docstring
    
    def _analyze_function_behavior(self, func_info: Dict, parse_result: Dict[str, Any]) -> str:
        """Analyze function code to generate descriptive summary."""
        if not parse_result:
            return None
        
        func_name = func_info['name']
        control_flow = parse_result.get('control_flow', [])
        function_calls = parse_result.get('function_calls', [])
        
        # Get control flow for this function
        func_flow = [cf for cf in control_flow if cf.get('function') == func_name]
        func_calls = [call for call in function_calls if call.get('caller') == func_name]
        
        # Also get method calls
        method_calls = parse_result.get('method_calls', [])
        func_method_calls = [call for call in method_calls if call.get('caller') == func_name]
        
        main_action = None
        secondary_actions = []
        exception_handling = []
        
        # Analyze with statements first (context managers)
        with_statements = [cf for cf in func_flow if cf.get('type') == 'with']
        for with_stmt in with_statements:
            items = with_stmt.get('items', [])
            if items:
                context = items[0].get('context', '').lower()
                if 'microphone' in context or 'mic' in context:
                    main_action = "Takes microphone input from the user"
                elif 'file' in context or 'open' in context:
                    main_action = "Opens and manages file resources"
                elif 'connection' in context or 'socket' in context:
                    main_action = "Manages network connections"
        
        # Analyze function calls to understand what the function does
        unique_calls = set()
        for call in func_calls:
            callee = call.get('callee', '').lower()
            unique_calls.add(callee)
        
        # Also add method calls
        for call in func_method_calls:
            class_name = call.get('class_name', '')
            method = call.get('method', '')
            if class_name and method:
                unique_calls.add(f"{class_name}.{method}".lower())
            elif method:
                unique_calls.add(method.lower())
        
        # Determine main action from function calls
        if not main_action:
            if any('listen' in c for c in unique_calls):
                main_action = "Takes microphone input from the user"
            elif any('recognize' in c for c in unique_calls):
                if not main_action:
                    main_action = "Recognizes speech input"
            elif any('speak' in c or 'say' in c for c in unique_calls):
                main_action = "Speaks output to the user"
            elif any('read' in c for c in unique_calls):
                main_action = "Reads data from a source"
            elif any('write' in c for c in unique_calls):
                main_action = "Writes data to a destination"
            elif any('print' in c for c in unique_calls):
                secondary_actions.append("prints output")
        
        # Analyze return behavior - skip for simple math functions (handled in fallback)
        return_statements = [cf for cf in func_flow if cf.get('type') == 'return']
        if return_statements and func_name.lower() not in ['add', 'subtract', 'multiply', 'divide', 'sub', 'mul', 'div']:
            has_value = any(rs.get('has_value') for rs in return_statements)
            if has_value:
                if 'recognize' in str(unique_calls).lower() or 'text' in func_name.lower() or 'command' in func_name.lower():
                    secondary_actions.append("returns it as text")
                else:
                    secondary_actions.append("returns the result")
        
        # Analyze try/except blocks for exception handling description
        try_blocks = [cf for cf in func_flow if cf.get('type') == 'try']
        if try_blocks:
            all_exceptions = []
            for try_block in try_blocks:
                excs = try_block.get('exceptions', [])
                all_exceptions.extend(excs)
            
            if all_exceptions:
                unique_exceptions = [e for e in set(all_exceptions) if e != 'Exception']
                if unique_exceptions:
                    # Clean exception names (remove module prefix like "sr.")
                    clean_exceptions = []
                    for exc in unique_exceptions:
                        # Extract just the exception class name (last part after dot)
                        if '.' in exc:
                            clean_exceptions.append(exc.split('.')[-1])
                        else:
                            clean_exceptions.append(exc)
                    
                    # Create natural exception description
                    if len(clean_exceptions) == 1:
                        exc_name = clean_exceptions[0]
                        if 'timeout' in exc_name.lower():
                            exception_handling.append("Handles timeout errors")
                        elif 'value' in exc_name.lower() or 'unknown' in exc_name.lower():
                            exception_handling.append("Handles recognition errors")
                        elif 'request' in exc_name.lower():
                            exception_handling.append("Handles request errors")
                        else:
                            exception_handling.append(f"Handles {exc_name}")
                    elif len(clean_exceptions) == 2:
                        # Format: "Handles UnknownValueError and RequestError"
                        exc1 = clean_exceptions[0]
                        exc2 = clean_exceptions[1]
                        exception_handling.append(f"Handles {exc1} and {exc2}")
                    else:
                        # Format: "Handles A, B, and C"
                        exception_handling.append(f"Handles {', '.join(clean_exceptions[:-1])}, and {clean_exceptions[-1]}")
                else:
                    exception_handling.append("Handles exceptions")
        
        # Build the description - prioritize main action, then return info, then exceptions
        parts = []
        if main_action:
            parts.append(main_action)
        
        # Add return information if available
        return_info = None
        return_statements = [cf for cf in func_flow if cf.get('type') == 'return']
        if return_statements:
            has_value = any(rs.get('has_value') for rs in return_statements)
            if has_value:
                if 'recognize' in str(unique_calls).lower() or 'text' in func_name.lower() or 'command' in func_name.lower():
                    return_info = "returns it as text"
                else:
                    return_info = "returns the result"
        
        if return_info:
            parts.append(return_info)
        
        # Add exception handling at the end
        if exception_handling:
            parts.extend(exception_handling)
        
        if parts:
            # For simple functions with just "returns the result", return None to use fallback
            if len(parts) == 1 and parts[0] == "returns the result":
                # Check if it's a simple math function - use fallback instead
                if func_name.lower() in ['add', 'subtract', 'multiply', 'divide', 'sub', 'mul', 'div']:
                    return None
            
            # Create a coherent sentence
            if len(parts) == 1:
                return parts[0] + "."
            elif len(parts) == 2:
                # Check if second part already starts with "Handles"
                if parts[1].startswith("Handles"):
                    return f"{parts[0]}. {parts[1]}."
                else:
                    return f"{parts[0]} and {parts[1]}."
            else:
                main = parts[0]
                # Separate exception handling from other parts
                exception_parts = [p for p in parts[1:] if p.startswith("Handles")]
                other_parts = [p for p in parts[1:] if not p.startswith("Handles")]
                
                if other_parts:
                    if len(other_parts) == 1:
                        sentence = f"{main} and {other_parts[0]}."
                    else:
                        middle = ", ".join(other_parts[:-1])
                        sentence = f"{main}, {middle}, and {other_parts[-1]}."
                else:
                    sentence = f"{main}."
                
                # Add exception handling as separate sentence
                if exception_parts:
                    if len(exception_parts) == 1:
                        sentence += f" {exception_parts[0]}."
                    else:
                        sentence += f" {', '.join(exception_parts)}."
                
                return sentence
        
        return None
    
    def _generate_parameter_description(self, param: str, func_info: Dict, parse_result: Dict[str, Any]) -> str:
        """Generate descriptive parameter documentation."""
        param_lower = param.lower()
        func_name_lower = func_info['name'].lower()
        
        # Common parameter patterns with context from function name
        if param_lower == 'a' and ('add' in func_name_lower or 'sum' in func_name_lower or 'multiply' in func_name_lower):
            return f"The first number to {func_info['name'].replace('_', ' ')}."
        elif param_lower == 'b' and ('add' in func_name_lower or 'sum' in func_name_lower or 'multiply' in func_name_lower):
            return f"The second number to {func_info['name'].replace('_', ' ')}."
        elif param_lower in ['x', 'y', 'num', 'number', 'value', 'val']:
            return f"The {param} value to process."
        elif 'file' in param_lower or 'path' in param_lower:
            return f"Path to the file to {func_info['name'].replace('_', ' ')}."
        elif 'url' in param_lower:
            return f"The URL to {func_info['name'].replace('_', ' ')}."
        elif 'data' in param_lower or 'input' in param_lower:
            return f"The input data to process."
        elif 'output' in param_lower or 'result' in param_lower:
            return f"The output result."
        elif 'config' in param_lower or 'settings' in param_lower:
            return f"Configuration settings."
        elif 'timeout' in param_lower:
            return f"Timeout duration in seconds."
        elif 'source' in param_lower:
            return f"The source to read from."
        elif 'target' in param_lower or 'dest' in param_lower:
            return f"The target destination."
        else:
            return f"The {param.replace('_', ' ')} parameter."
    
    def _analyze_return_behavior(self, func_info: Dict, parse_result: Dict[str, Any]) -> str:
        """Analyze what the function returns."""
        if not parse_result:
            return None
        
        func_name = func_info['name']
        control_flow = parse_result.get('control_flow', [])
        func_flow = [cf for cf in control_flow if cf.get('function') == func_name]
        
        return_statements = [cf for cf in func_flow if cf.get('type') == 'return']
        
        if not return_statements:
            return None
        
        # Check function name for clues
        func_name_lower = func_name.lower()
        if 'get' in func_name_lower or 'fetch' in func_name_lower or 'retrieve' in func_name_lower or 'take' in func_name_lower:
            if 'text' in func_name_lower or 'speech' in func_name_lower or 'command' in func_name_lower:
                return "str: The recognized text as a string, or None if recognition fails."
            return "The retrieved value."
        elif 'check' in func_name_lower or 'is' in func_name_lower or 'has' in func_name_lower:
            return "bool: True if the condition is met, False otherwise."
        elif 'calculate' in func_name_lower or 'compute' in func_name_lower or 'add' in func_name_lower or 'sum' in func_name_lower:
            return "The calculated result."
        elif 'create' in func_name_lower or 'make' in func_name_lower:
            return "The created object or value."
        elif 'process' in func_name_lower or 'handle' in func_name_lower:
            return "The processed result."
        
        # Default based on return type annotation
        if func_info.get('returns'):
            return_type = func_info['returns']
            if return_type == 'str':
                return "str: The result as a string."
            elif return_type == 'int':
                return "int: The result as an integer."
            elif return_type == 'bool':
                return "bool: The boolean result."
            elif return_type == 'list':
                return "list: A list of results."
            elif return_type == 'dict':
                return "dict: A dictionary of results."
            else:
                return f"{return_type}: The result value."
        
        # Check if function can return None (has multiple return paths)
        has_none_return = any(not rs.get('has_value') for rs in return_statements)
        has_value_return = any(rs.get('has_value') for rs in return_statements)
        
        if has_none_return and has_value_return:
            return "The function result, or None if an error occurs."
        
        return "The function result."
    
    def _analyze_exceptions(self, func_info: Dict, parse_result: Dict[str, Any]) -> List[str]:
        """Analyze what exceptions the function handles/raises."""
        if not parse_result:
            return []
        
        func_name = func_info['name']
        control_flow = parse_result.get('control_flow', [])
        func_flow = [cf for cf in control_flow if cf.get('function') == func_name]
        
        try_blocks = [cf for cf in func_flow if cf.get('type') == 'try']
        exceptions = []
        seen_exceptions = set()
        
        for try_block in try_blocks:
            excs = try_block.get('exceptions', [])
            for exc in excs:
                if exc not in seen_exceptions and exc != 'Exception':
                    seen_exceptions.add(exc)
                    # Clean exception name (remove module prefix)
                    exc_name = exc.split('.')[-1] if '.' in exc else exc
                    # Generate description for each exception
                    exc_lower = exc_name.lower()
                    if 'timeout' in exc_lower:
                        exceptions.append(f"TimeoutError: If the operation times out.")
                    elif 'value' in exc_lower or 'unknown' in exc_lower:
                        exceptions.append(f"{exc_name}: If the input cannot be recognized or is invalid.")
                    elif 'request' in exc_lower or 'connection' in exc_lower:
                        exceptions.append(f"{exc_name}: If there is a network or request error.")
                    elif 'file' in exc_lower or 'io' in exc_lower:
                        exceptions.append(f"{exc_name}: If there is a file I/O error.")
                    elif 'permission' in exc_lower or 'access' in exc_lower:
                        exceptions.append(f"{exc_name}: If access is denied.")
                    else:
                        exceptions.append(f"{exc_name}: If an error occurs during execution.")
        
        return exceptions
    
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

