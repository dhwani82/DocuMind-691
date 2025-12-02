import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from svg_generator import SVGFlowchartGenerator
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
svg_gen = SVGFlowchartGenerator(result)
svg = svg_gen.generate_svg_flowchart()

# Save to file
output_path = os.path.join(os.path.dirname(__file__), 'test_flowchart.svg')
with open(output_path, 'w') as f:
    f.write(svg)

print("SVG file created: test_flowchart.svg")
print(f"SVG size: {len(svg)} characters")

