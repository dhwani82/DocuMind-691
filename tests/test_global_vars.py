#!/usr/bin/env python3
"""Test script to verify global variable parsing."""

# These should be global variables
GLOBAL_CONSTANT = 42
module_level_var = "hello"
ANOTHER_GLOBAL = [1, 2, 3]

def test_function():
    # These should NOT be global variables (local to function)
    local_var = 10
    another_local = "test"
    return local_var

class TestClass:
    # This should be a class variable
    class_var = "class_value"
    
    def __init__(self):
        # This should be an instance variable
        self.instance_var = "instance_value"
        
    def method(self):
        # This should NOT be a global variable (local to method)
        method_local = 99
        return method_local

if __name__ == "__main__":
    # This should be a global variable
    main_var = "main"
    print("Test completed")

