"""
Example Python file for testing DocuMind
This file demonstrates various Python constructs
"""

import os
import json
from typing import List, Dict, Optional

# Global variables
GLOBAL_CONSTANT = 42
global_list = [1, 2, 3]

def sync_function(param1: str, param2: int = 10) -> str:
    """A regular synchronous function."""
    local_var = "test"
    return f"{param1}: {param2}"

async def async_function(data: List[str]) -> Dict:
    """An async function."""
    result = {}
    for item in data:
        result[item] = len(item)
    return result

def outer_function():
    """Function with nested function."""
    nested_var = "nested"
    
    def nested_function():
        """A nested function."""
        return nested_var
    
    return nested_function()

@staticmethod
def decorated_function():
    """A function with decorator."""
    return "decorated"

class BaseClass:
    """A base class."""
    class_var = "class variable"
    
    def __init__(self, name: str):
        self.name = name
        self.instance_var = "instance"
    
    def instance_method(self):
        """An instance method."""
        return self.name
    
    @classmethod
    def class_method(cls):
        """A class method."""
        return cls.class_var

class DerivedClass(BaseClass):
    """A derived class."""
    derived_class_var = "derived"
    
    def __init__(self, name: str, value: int):
        super().__init__(name)
        self.value = value
    
    async def async_method(self):
        """An async method."""
        return await async_function([self.name])

