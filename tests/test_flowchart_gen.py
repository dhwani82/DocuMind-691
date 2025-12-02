import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_parser import CodeParser
from diagram_generator import DiagramGenerator

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
diagram_gen = DiagramGenerator(result)
flowchart = diagram_gen.generate_flowchart()
print(flowchart)

