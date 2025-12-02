import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_parser import CodeParser

code = """
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
"""

parser = CodeParser()
result = parser.parse(code)
print(f"Functions: {len(result['functions'])}")
print(f"Control flow items: {len(result.get('control_flow', []))}")
for cf in result.get('control_flow', []):
    print(f"  {cf}")

