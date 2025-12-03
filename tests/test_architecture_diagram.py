"""Test cases for architecture diagram generation."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from code_parser import CodeParser
from diagram_generator import DiagramGenerator


def test_functional_code_no_classes():
    """Test architecture diagram for code without classes."""
    code = '''
import os
import sys
from typing import List, Dict, Optional

# Global variables
API_KEY = "secret_key"
MAX_RETRIES = 3
config = {"debug": True}

def fetch_data(url: str) -> Dict:
    """Fetch data from URL."""
    return {"status": "ok"}

def process_data(data: List) -> List:
    """Process a list of data items."""
    return [item * 2 for item in data]

async def async_fetch(url: str):
    """Async fetch function."""
    return {"async": True}

if __name__ == '__main__':
    result = fetch_data("https://api.example.com")
    processed = process_data([1, 2, 3])
    print(f"Result: {result}, Processed: {processed}")
'''
    
    parser = CodeParser()
    result = parser.parse(code)
    diagram_gen = DiagramGenerator(result)
    arch = diagram_gen.generate_architecture_diagram()
    
    print("=" * 80)
    print("TEST 1: Functional Code (No Classes)")
    print("=" * 80)
    print(arch)
    print()
    
    # Verify structure
    assert "MODULE" in arch
    assert "Imports" in arch
    # Check for categorized sections (Helpers, Services, etc.)
    assert "Helpers" in arch or "Services" in arch or "Components" in arch
    assert "Global Variables" in arch
    assert "Execution Scope" in arch or "Execution Entry Point" in arch
    
    return arch


def test_code_with_classes():
    """Test architecture diagram for code with classes."""
    code = '''
import os
from abc import ABC, abstractmethod
from typing import List

class Animal(ABC):
    """Base animal class."""
    species = "unknown"
    
    @abstractmethod
    def make_sound(self):
        """Make a sound."""
        pass
    
    def sleep(self):
        """Sleep."""
        return "zzz"

class Dog(Animal):
    """Dog class."""
    species = "Canis lupus"
    
    def __init__(self, name: str):
        self.name = name
    
    def make_sound(self):
        return "Woof!"
    
    def fetch(self, item: str):
        return f"{self.name} fetched {item}"

class Cat(Animal):
    """Cat class."""
    species = "Felis catus"
    
    def make_sound(self):
        return "Meow!"
    
    def climb(self):
        return "Climbing tree"

def create_pet(pet_type: str, name: str):
    """Factory function to create pets."""
    if pet_type == "dog":
        return Dog(name)
    elif pet_type == "cat":
        return Cat(name)
    return None

if __name__ == '__main__':
    dog = Dog("Buddy")
    cat = Cat()
    print(dog.make_sound())
    print(cat.make_sound())
'''
    
    parser = CodeParser()
    result = parser.parse(code)
    diagram_gen = DiagramGenerator(result)
    arch = diagram_gen.generate_architecture_diagram()
    
    print("=" * 80)
    print("TEST 2: Code with Classes and Inheritance")
    print("=" * 80)
    print(arch)
    print()
    
    # Verify structure
    assert "MODULE" in arch
    # Check for categorized sections
    assert "Models" in arch or "Services" in arch or "Components" in arch
    assert "Animal" in arch
    assert "Dog" in arch
    assert "Cat" in arch
    assert "inherits" in arch
    
    return arch


def test_mixed_code():
    """Test architecture diagram for mixed code (classes + functions + globals)."""
    code = '''
import json
import requests
from datetime import datetime

# Configuration
API_BASE_URL = "https://api.example.com"
TIMEOUT = 30

class APIClient:
    """Client for API interactions."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = API_BASE_URL
    
    def get(self, endpoint: str):
        """GET request."""
        return {"data": "response"}
    
    def post(self, endpoint: str, data: dict):
        """POST request."""
        return {"status": "created"}

def validate_response(response: dict) -> bool:
    """Validate API response."""
    return "data" in response or "status" in response

def format_timestamp() -> str:
    """Get formatted timestamp."""
    return datetime.now().isoformat()

if __name__ == '__main__':
    client = APIClient("test_key")
    response = client.get("/users")
    is_valid = validate_response(response)
    print(f"Valid: {is_valid}")
'''
    
    parser = CodeParser()
    result = parser.parse(code)
    diagram_gen = DiagramGenerator(result)
    arch = diagram_gen.generate_architecture_diagram()
    
    print("=" * 80)
    print("TEST 3: Mixed Code (Classes + Functions + Globals)")
    print("=" * 80)
    print(arch)
    print()
    
    # Verify all components
    assert "MODULE" in arch
    assert "Imports" in arch
    # Check for categorized sections
    assert "Models" in arch or "Services" in arch or "Components" in arch
    assert "Global Variables" in arch
    assert "Execution Scope" in arch or "Execution Entry Point" in arch
    
    return arch


def test_empty_code():
    """Test architecture diagram for empty code."""
    code = ''
    
    parser = CodeParser()
    result = parser.parse(code)
    diagram_gen = DiagramGenerator(result)
    arch = diagram_gen.generate_architecture_diagram()
    
    print("=" * 80)
    print("TEST 4: Empty Code")
    print("=" * 80)
    print(arch)
    print()
    
    # Should at least show module
    assert "MODULE" in arch
    
    return arch


def test_only_imports():
    """Test architecture diagram for code with only imports."""
    code = '''
import os
import sys
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
import requests
'''
    
    parser = CodeParser()
    result = parser.parse(code)
    diagram_gen = DiagramGenerator(result)
    arch = diagram_gen.generate_architecture_diagram()
    
    print("=" * 80)
    print("TEST 5: Only Imports")
    print("=" * 80)
    print(arch)
    print()
    
    # Should show module and imports
    assert "MODULE" in arch
    assert "Imports" in arch
    
    return arch


def test_nested_functions():
    """Test architecture diagram with nested functions."""
    code = '''
import os

def outer_function(x: int):
    """Outer function."""
    def inner_function(y: int):
        """Inner function."""
        return y * 2
    
    return inner_function(x)

def top_level_function():
    """Top-level function."""
    return "top level"

if __name__ == '__main__':
    result = outer_function(5)
    print(result)
'''
    
    parser = CodeParser()
    result = parser.parse(code)
    diagram_gen = DiagramGenerator(result)
    arch = diagram_gen.generate_architecture_diagram()
    
    print("=" * 80)
    print("TEST 6: Nested Functions (only top-level shown)")
    print("=" * 80)
    print(arch)
    print()
    
    # Should only show top-level functions in categorized sections
    assert "outer_function" in arch or "top_level_function" in arch
    # inner_function should not appear (it's nested)
    
    return arch


def test_complex_inheritance():
    """Test architecture diagram with complex inheritance."""
    code = '''
from abc import ABC, abstractmethod

class BaseClass(ABC):
    """Base class."""
    def base_method(self):
        return "base"

class IntermediateClass(BaseClass):
    """Intermediate class."""
    def intermediate_method(self):
        return "intermediate"

class FinalClass(IntermediateClass):
    """Final derived class."""
    def final_method(self):
        return "final"

def utility_function():
    """Utility function."""
    return "utility"
'''
    
    parser = CodeParser()
    result = parser.parse(code)
    diagram_gen = DiagramGenerator(result)
    arch = diagram_gen.generate_architecture_diagram()
    
    print("=" * 80)
    print("TEST 7: Complex Inheritance Chain")
    print("=" * 80)
    print(arch)
    print()
    
    # Verify inheritance chain (should be in Models or Components section)
    assert "BaseClass" in arch
    assert "IntermediateClass" in arch
    assert "FinalClass" in arch
    assert "inherits" in arch
    
    return arch


def test_simple_example():
    """Simple test case with minimal code to verify basic categorization."""
    code = '''
class User:
    """User model."""
    pass

class UserService:
    """Service for user operations."""
    pass

def main():
    """Entry point."""
    pass
'''
    
    parser = CodeParser()
    result = parser.parse(code)
    diagram_gen = DiagramGenerator(result)
    arch = diagram_gen.generate_architecture_diagram()
    
    print("=" * 80)
    print("TEST 8: Simple Example (Minimal Code)")
    print("=" * 80)
    print(arch)
    print()
    
    # Verify basic structure
    assert "MODULE" in arch
    assert "User" in arch
    assert "UserService" in arch
    assert "main" in arch
    
    return arch


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("ARCHITECTURE DIAGRAM TEST SUITE")
    print("=" * 80 + "\n")
    
    try:
        test_functional_code_no_classes()
        test_code_with_classes()
        test_mixed_code()
        test_empty_code()
        test_only_imports()
        test_nested_functions()
        test_complex_inheritance()
        test_simple_example()
        
        print("=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

