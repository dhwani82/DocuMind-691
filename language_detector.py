"""
Language detection utility with file extension priority.

File extensions align with :mod:`universal_parser` (EXT_TO_LANG) so Java, Go, Rust, etc.
resolve before broken content heuristics. Content fallbacks use distinctive markers
so Java/Go/… are not misclassified as Python (``import``) or JavaScript (``import``).
"""

import re
from typing import Optional, Dict, List, Tuple

from universal_parser import EXT_TO_LANG

# Subset: allowed manual overrides in /api/parse (dropdown + validation)
NORMALIZED_LANGUAGES = ('python', 'javascript', 'cpp', 'c', 'sql')


class LanguageDetector:
    """Detect programming language with file extension priority."""

    # Single source: shared with universal_parser for consistent routing
    EXTENSION_MAP: Dict[str, str] = {**EXT_TO_LANG}

    # Scoring patterns when there is no filename / unknown extension
    # Keys match parse_code_auto routing: python, javascript, sql, c, cpp, else universal
    LANGUAGE_PATTERNS: Dict[str, List[re.Pattern]] = {
        'python': [
            re.compile(r'^\s*from\s+\w+(\.\w+)*\s+import\s+', re.MULTILINE),
            # Java/Kotlin use semicolons; Python import lines should not
            re.compile(
                r"^\s*import(?!\s+static)(?!\s+java\.)[ \t]*[^#\n;]+(?:#.*)?$", re.M
            ),
            re.compile(r'^\s*def\s+\w+\s*\('),
            re.compile(r'^\s*class\s+\w+(\(|:)'),
            re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']'),
            re.compile(r'^\s*@\w+\s*(?:\n|def|class)'),
        ],
        'javascript': [
            re.compile(r"^\s*import\s+[\w*{},\s]+\s+from\s+['\"]", re.MULTILINE),
            re.compile(r"^\s*export\s+(?:default|const|function|class|type)\s+", re.MULTILINE),
            re.compile(r"\b=>\s*[{(\n]"),
            re.compile(r"require\s*\(\s*['\"]", re.M),
            re.compile(r"console\.(log|error|warn|info)\s*\("),
        ],
        'cpp': [
            re.compile(r'#include\s*[<"]'),
            re.compile(r"\bstd::\w+"),
            re.compile(r"\b(cout|cin)\b"),
            re.compile(r"\bnamespace\s+\w+"),
        ],
        'c': [
            re.compile(r'#include\s*[<"]'),
            re.compile(r"\b(printf|scanf|malloc|free|strcpy|memcpy)\s*\("),
        ],
        'sql': [
            re.compile(r'\bCREATE\s+TABLE\b', re.IGNORECASE),
            re.compile(r"\bSELECT\s+.+\bFROM\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE),
        ],
        'java': [
            re.compile(r'^\s*import\s+java\.', re.M),
            re.compile(r"^\s*package\s+[\w.]+\s*;\s*$", re.M),
            re.compile(r"\bpublic\s+class\s+\w+"),
            re.compile(r"\bpublic\s+static\s+void\s+main"),
        ],
        'go': [
            re.compile(r"^\s*package\s+[\w.]+\s*$", re.M),
            re.compile(r"^\s*func\s+(\w+|\(\s*[\w*]+\s*[\w.]+\s*\))", re.M),
        ],
        'rust': [
            re.compile(r"^\s*(?:pub\s+)?fn\s+\w+\s*\(", re.M),
            re.compile(r"^\s*use\s+[\w:]+\s*;\s*$", re.M),
            re.compile(r"^\s*(?:pub\s+)?(?:struct|enum|impl|trait)\s+\w+", re.M),
        ],
        'ruby': [
            re.compile(r"^\s*require[_ ]+['\"]", re.M),
            re.compile(r"^\s*require_relative\s+['\"]", re.M),
            re.compile(r"^\s*module\s+\w+\s*$\n", re.M),
        ],
        'php': [
            re.compile(r"<\?php"),
        ],
    }

    # When scores tie, prefer more specific language IDs (not alphabetical)
    _TIE_PREFERENCE: Tuple[str, ...] = (
        "php",
        "java",
        "go",
        "rust",
        "sql",
        "python",  # before ruby — do not use overlapping def/class for ruby
        "ruby",
        "javascript",
        "cpp",
        "c",
    )

    @classmethod
    def _preamble_guess(cls, code: str) -> Optional[str]:
        """High-confidence language markers from the first part of a file."""
        h = (code or "")[:16000]
        # Python: trailing colon on def/class (Ruby defs do not use this)
        if re.search(r"^\s*def\s+\w+\s*\([^\n]*\)\s*:", h, re.M):
            return "python"
        if re.search(r"^\s*class\s+\w+[^:\n]*:\s*$\n(?:[ \t]+def|from\s+)", h, re.M | re.MULTILINE):
            return "python"
        if re.search(r"^\s*from\s+\w+(\.\w+)*\s+import\s+", h, re.M):
            return "python"
        if re.search(r"^\s*<\?php", h, re.M):
            return "php"
        if re.search(r"^\s*package\s+[\w.]+\s*;\s", h) and re.search(
            r"(?:\bimport\s+java\.|\bpublic\s+class\s+\w+)", h
        ):
            return "java"
        if re.search(r"^\s*package\s+[\w.]+\s*$", h, re.M) and re.search(
            r"^\s*func\s+(?:\w+|\()", h, re.M
        ):
            return "go"
        if re.search(
            r"^\s*use\s+[\w:]*std::|^\s*(?:pub\s+)?mod\s+\w+", h, re.M
        ) or re.search(r"^#!\[", h, re.M):
            return "rust"
        return None

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

        pre = cls._preamble_guess(code)
        if pre:
            return pre
        
        # Score each language based on pattern matches
        scores: Dict[str, int] = {}
        
        for language, patterns in cls.LANGUAGE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                score += len(pattern.findall(code))
            if score > 0:
                scores[language] = score
        
        if not scores:
            return None

        best = max(scores.values())
        cands = [k for k, v in scores.items() if v == best]
        if len(cands) == 1:
            return cands[0]
        for lang in cls._TIE_PREFERENCE:
            if lang in cands:
                return lang
        return cands[0]
    
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
            return language.lower() in NORMALIZED_LANGUAGES
        
        return False

