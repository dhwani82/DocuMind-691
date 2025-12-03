"""
Language detection utility with file extension priority.

This module provides language detection that prioritizes file extensions
over other detection methods, making it more reliable and faster.
"""

import re
from typing import Optional, Dict, List, Tuple


class LanguageDetector:
    """Detect programming language with file extension priority."""
    
    # Extension to language mapping (priority order)
    EXTENSION_MAP: Dict[str, str] = {
        # Python
        '.py': 'python',
        '.pyw': 'python',
        '.pyi': 'python',
        
        # JavaScript/TypeScript
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.mjs': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        
        # Java
        '.java': 'java',
        '.class': 'java',
        
        # C/C++
        '.c': 'c',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.hxx': 'cpp',
        
        # C#
        '.cs': 'csharp',
        
        # Go
        '.go': 'go',
        
        # Rust
        '.rs': 'rust',
        
        # Ruby
        '.rb': 'ruby',
        '.rbw': 'ruby',
        
        # PHP
        '.php': 'php',
        '.phtml': 'php',
        
        # Swift
        '.swift': 'swift',
        
        # Kotlin
        '.kt': 'kotlin',
        '.kts': 'kotlin',
        
        # Scala
        '.scala': 'scala',
        '.sc': 'scala',
        
        # R
        '.r': 'r',
        '.R': 'r',
        
        # Shell scripts
        '.sh': 'bash',
        '.bash': 'bash',
        '.zsh': 'bash',
        
        # HTML/CSS
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        
        # Markdown
        '.md': 'markdown',
        '.markdown': 'markdown',
        
        # JSON
        '.json': 'json',
        
        # XML
        '.xml': 'xml',
        
        # YAML
        '.yaml': 'yaml',
        '.yml': 'yaml',
        
        # SQL
        '.sql': 'sql',
    }
    
    # Language-specific patterns for fallback detection (when no extension)
    LANGUAGE_PATTERNS: Dict[str, List[re.Pattern]] = {
        'python': [
            re.compile(r'\b(?:def|class|import|from|if\s+__name__)\s+'),
            re.compile(r'\b(?:print|len|range|str|int|list|dict)\s*\('),
            re.compile(r'#.*python', re.IGNORECASE),
        ],
        'javascript': [
            re.compile(r'\b(?:function|const|let|var|=>|require\(|import\s)'),
            re.compile(r'console\.(log|error|warn)'),
            re.compile(r'/\*.*\*/|//'),
        ],
        'java': [
            re.compile(r'\b(?:public|private|class|interface|package)\s+'),
            re.compile(r'\b(?:System\.out\.print|import\s+java\.)'),
        ],
        'cpp': [
            re.compile(r'#include\s*[<"]'),
            re.compile(r'\b(?:using\s+namespace|std::|cout\s*<<)'),
        ],
        'c': [
            re.compile(r'#include\s*[<"]'),
            re.compile(r'\b(?:printf|scanf|malloc|free)\s*\('),
        ],
        'sql': [
            re.compile(r'\bCREATE\s+TABLE\b', re.IGNORECASE),
            re.compile(r'\bSELECT\s+.*\bFROM\b', re.IGNORECASE),
            re.compile(r'\bINSERT\s+INTO\b', re.IGNORECASE),
            re.compile(r'\bFOREIGN\s+KEY\b', re.IGNORECASE),
            re.compile(r'\bPRIMARY\s+KEY\b', re.IGNORECASE),
        ],
    }
    
    @classmethod
    def detect_from_extension(cls, filename: str) -> Optional[str]:
        """Detect language from file extension (highest priority).
        
        Args:
            filename: Name of the file (can be just extension or full path)
            
        Returns:
            Language name if detected, None otherwise
        """
        if not filename:
            return None
        
        # Extract extension
        filename_lower = filename.lower()
        
        # Check for extension (including multiple dots like .tar.gz)
        # Try longest extensions first
        extensions = sorted(cls.EXTENSION_MAP.keys(), key=len, reverse=True)
        
        for ext in extensions:
            if filename_lower.endswith(ext):
                return cls.EXTENSION_MAP[ext]
        
        return None
    
    @classmethod
    def detect_from_code(cls, code: str) -> Optional[str]:
        """Detect language from code content (fallback method).
        
        Args:
            code: Source code content
            
        Returns:
            Language name if detected, None otherwise
        """
        if not code or len(code.strip()) == 0:
            return None
        
        # Score each language based on pattern matches
        scores: Dict[str, int] = {}
        
        for language, patterns in cls.LANGUAGE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = pattern.findall(code)
                score += len(matches)
            if score > 0:
                scores[language] = score
        
        if not scores:
            return None
        
        # Return language with highest score
        return max(scores.items(), key=lambda x: x[1])[0]
    
    @classmethod
    def detect(cls, filename: Optional[str] = None, code: Optional[str] = None) -> Optional[str]:
        """Detect language with file extension priority.
        
        Priority order:
        1. File extension (highest priority)
        2. Code content analysis (fallback)
        
        Args:
            filename: Name of the file (optional)
            code: Source code content (optional)
            
        Returns:
            Detected language name, or None if cannot detect
        """
        # Priority 1: File extension
        if filename:
            language = cls.detect_from_extension(filename)
            if language:
                return language
        
        # Priority 2: Code content analysis (fallback)
        if code:
            language = cls.detect_from_code(code)
            if language:
                return language
        
        return None
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get list of all supported file extensions.
        
        Returns:
            List of file extensions (with dots)
        """
        return sorted(cls.EXTENSION_MAP.keys())
    
    @classmethod
    def is_supported(cls, filename: Optional[str] = None, language: Optional[str] = None) -> bool:
        """Check if a file or language is supported.
        
        Args:
            filename: Name of the file to check
            language: Language name to check
            
        Returns:
            True if supported, False otherwise
        """
        if filename:
            detected = cls.detect_from_extension(filename)
            return detected is not None
        
        if language:
            return language.lower() in [lang.lower() for lang in cls.EXTENSION_MAP.values()]
        
        return False

