"""Sample project used by the Phase E evaluation golden set."""

from pathlib import Path

from tests.sample_code_for_testing import (
    SAMPLE_CLASS,
    SAMPLE_INHERITANCE,
    SAMPLE_MIXED,
    SAMPLE_SIMPLE_FUNCTIONS,
)

SAMPLE_CALLS = '''
def helper():
    return 1

def main():
    return helper()
'''

SAMPLE_FILES = {
    "mixed.py": SAMPLE_MIXED,
    "inheritance.py": SAMPLE_INHERITANCE,
    "calls.py": SAMPLE_CALLS,
    "simple.py": SAMPLE_SIMPLE_FUNCTIONS,
    "calculator.py": SAMPLE_CLASS,
}


def ensure_sample_project(target_dir: Path) -> Path:
    """Materialize the eval sample project on disk."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for name, content in SAMPLE_FILES.items():
        path = target_dir / name
        path.write_text(content.strip() + "\n", encoding="utf-8")
    return target_dir.resolve()
