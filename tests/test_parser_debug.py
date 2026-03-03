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

print("Functions:", result.get("functions"))
print("Function Count:", len(result.get("functions", [])))
print("Classes:", result.get("classes"))
print("Summary:", result.get("summary"))
