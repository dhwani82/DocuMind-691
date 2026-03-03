"""
Sample code snippets for testing DocuMind parser and doc generator.
Copy any block below into the app or test_parser_debug.py.
"""

# ---------------------------------------------------------------------------
# Sample 1: Simple functions (good for basic parse/debug)
# ---------------------------------------------------------------------------
SAMPLE_SIMPLE_FUNCTIONS = '''
def test_function(x):
    if x > 0:
        return 1
    else:
        return 0

def loop_example(items):
    result = []
    for item in items:
        if item > 5:
            result.append(item)
    return result
'''

# ---------------------------------------------------------------------------
# Sample 2: Class with methods
# ---------------------------------------------------------------------------
SAMPLE_CLASS = '''
class Calculator:
    def __init__(self):
        self.value = 0

    def add(self, x, y):
        return x + y

    def subtract(self, x, y):
        return x - y

    def reset(self):
        self.value = 0
'''

# ---------------------------------------------------------------------------
# Sample 3: Mixed – functions + class + imports
# ---------------------------------------------------------------------------
SAMPLE_MIXED = '''
import os
from pathlib import Path

def load_config(path):
    with open(path) as f:
        return f.read()

def save_result(data, filename):
    Path(filename).write_text(data)

class DataProcessor:
    def process(self, raw):
        return raw.strip().lower()

    def validate(self, data):
        return len(data) > 0
'''

# ---------------------------------------------------------------------------
# Sample 4: Nested function and async
# ---------------------------------------------------------------------------
SAMPLE_NESTED_ASYNC = '''
def outer(x):
    def inner(y):
        return x + y
    return inner(x * 2)

async def fetch_data(url):
    return await get(url)
'''

# ---------------------------------------------------------------------------
# Sample 5: Minimal (single function) – quick sanity check
# ---------------------------------------------------------------------------
SAMPLE_MINIMAL = '''
def hello(name):
    return f"Hello, {name}"
'''

# ---------------------------------------------------------------------------
# Sample 6: Multiple classes and inheritance
# ---------------------------------------------------------------------------
SAMPLE_INHERITANCE = '''
class Animal:
    def speak(self):
        pass

class Dog(Animal):
    def speak(self):
        return "Woof"

class Cat(Animal):
    def speak(self):
        return "Meow"
'''

# ---------------------------------------------------------------------------
# Usage in test_parser_debug.py:
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from code_parser import CodeParser

    # Pick one:
    code = SAMPLE_SIMPLE_FUNCTIONS
    # code = SAMPLE_CLASS
    # code = SAMPLE_MIXED
    # code = SAMPLE_MINIMAL
    # code = SAMPLE_INHERITANCE

    parser = CodeParser()
    result = parser.parse(code)
    print("Functions:", len(result.get("functions", [])))
    print("Classes:", len(result.get("classes", [])))
    print("Summary:", result.get("summary"))
