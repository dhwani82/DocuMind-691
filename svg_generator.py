"""Generate SVG flowcharts from parsed control flow."""
from typing import Dict, List, Any, Tuple, Optional


class SVGFlowchartGenerator:
    """Generate SVG flowcharts from control flow data."""
    
    def __init__(self, parse_result: Dict[str, Any]):
        """Initialize with parse results.
        
        Args:
            parse_result: Result from CodeParser.parse()
        """
        self.parse_result = parse_result
        self.functions = parse_result.get('functions', [])
        self.control_flow = parse_result.get('control_flow', [])
    
    def generate_svg_flowchart(self, function_name: str = None) -> str:
        """Generate SVG flowchart for a function.
        
        Args:
            function_name: Name of function to generate flowchart for.
            
        Returns:
            SVG code as string
        """
        # Get function to process
        if function_name:
            funcs = [f for f in self.functions if f['name'] == function_name]
        else:
            # Get top-level functions with most control flow
            funcs = [f for f in self.functions if not f.get('is_nested', False)]
            if funcs:
                funcs_with_flow = []
                for func in funcs:
                    func_name = func['name']
                    func_flow = [cf for cf in self.control_flow if cf.get('function') == func_name]
                    if func_flow:
                        funcs_with_flow.append((func, len(func_flow)))
                if funcs_with_flow:
                    funcs_with_flow.sort(key=lambda x: x[1], reverse=True)
                    funcs = [funcs_with_flow[0][0]]
        
        if not funcs:
            return self._generate_empty_svg("No functions found")
        
        func_info = funcs[0]
        func_name = func_info['name']
        func_flow = [cf for cf in self.control_flow if cf.get('function') == func_name]
        
        if not func_flow:
            return self._generate_empty_svg(f"Function '{func_name}' has no control flow structures")
        
        return self._generate_function_svg(func_name, func_flow)
    
    def _generate_function_svg(self, func_name: str, flow_items: List[Dict]) -> str:
        """Generate SVG for a single function's control flow."""
        # Sort flow items by line number
        flow_items = sorted(flow_items, key=lambda x: x.get('line', 0))
        
        # Build flowchart structure
        nodes = []
        connections = []
        x_center = 300
        y_start = 60
        
        # Start node
        start_node = {
            'id': 'start',
            'type': 'start',
            'text': f'Start: {func_name}',
            'x': x_center,
            'y': y_start,
            'width': 140,
            'height': 50
        }
        nodes.append(start_node)
        node_map = {'start': 0}
        
        current_y = y_start + 90
        current_node_id = 'start'
        node_counter = 1
        
        # Process flow items in order
        for i, flow in enumerate(flow_items):
            flow_type = flow.get('type')
            node_id = f'node_{node_counter}'
            
            if flow_type == 'if':
                condition = flow.get('condition', 'condition')
                has_else = flow.get('has_else', False)
                
                # Truncate long conditions
                if len(condition) > 40:
                    condition = condition[:37] + "..."
                
                # Decision node (diamond)
                decision_node = {
                    'id': node_id,
                    'type': 'decision',
                    'text': condition,
                    'x': x_center,
                    'y': current_y,
                    'width': max(160, len(condition) * 7),
                    'height': 70
                }
                nodes.append(decision_node)
                node_map[node_id] = len(nodes) - 1
                
                # Connect previous node to decision
                connections.append((current_node_id, node_id, None))
                
                current_y += 100
                
                # True branch
                true_node_id = f'{node_id}_true'
                true_node = {
                    'id': true_node_id,
                    'type': 'process',
                    'text': 'If Body',
                    'x': x_center - 180 if has_else else x_center,
                    'y': current_y,
                    'width': 120,
                    'height': 50
                }
                nodes.append(true_node)
                node_map[true_node_id] = len(nodes) - 1
                connections.append((node_id, true_node_id, 'True'))
                
                if has_else:
                    # False branch
                    false_node_id = f'{node_id}_false'
                    false_node = {
                        'id': false_node_id,
                        'type': 'process',
                        'text': 'Else Body',
                        'x': x_center + 180,
                        'y': current_y,
                        'width': 120,
                        'height': 50
                    }
                    nodes.append(false_node)
                    node_map[false_node_id] = len(nodes) - 1
                    connections.append((node_id, false_node_id, 'False'))
                    
                    current_y += 90
                    
                    # Merge point
                    merge_node_id = f'{node_id}_merge'
                    merge_node = {
                        'id': merge_node_id,
                        'type': 'process',
                        'text': 'Continue',
                        'x': x_center,
                        'y': current_y,
                        'width': 120,
                        'height': 50
                    }
                    nodes.append(merge_node)
                    node_map[merge_node_id] = len(nodes) - 1
                    connections.append((true_node_id, merge_node_id, None))
                    connections.append((false_node_id, merge_node_id, None))
                    current_node_id = merge_node_id
                else:
                    # No else - false goes directly to merge
                    current_y += 90
                    merge_node_id = f'{node_id}_merge'
                    merge_node = {
                        'id': merge_node_id,
                        'type': 'process',
                        'text': 'Continue',
                        'x': x_center,
                        'y': current_y,
                        'width': 120,
                        'height': 50
                    }
                    nodes.append(merge_node)
                    node_map[merge_node_id] = len(nodes) - 1
                    connections.append((true_node_id, merge_node_id, None))
                    connections.append((node_id, merge_node_id, 'False'))
                    current_node_id = merge_node_id
                
                current_y += 90
                node_counter += 1
            
            elif flow_type == 'for':
                target = flow.get('target', 'item')
                iter_expr = flow.get('iter', 'iterable')
                
                # Truncate long expressions
                if len(iter_expr) > 30:
                    iter_expr = iter_expr[:27] + "..."
                
                loop_text = f'for {target} in {iter_expr}'
                
                # Loop decision node
                loop_node = {
                    'id': node_id,
                    'type': 'decision',
                    'text': loop_text,
                    'x': x_center,
                    'y': current_y,
                    'width': max(180, len(loop_text) * 7),
                    'height': 70
                }
                nodes.append(loop_node)
                node_map[node_id] = len(nodes) - 1
                
                # Connect previous node to loop
                connections.append((current_node_id, node_id, None))
                
                current_y += 100
                
                # Loop body
                body_node_id = f'{node_id}_body'
                body_node = {
                    'id': body_node_id,
                    'type': 'process',
                    'text': 'Loop Body',
                    'x': x_center,
                    'y': current_y,
                    'width': 120,
                    'height': 50
                }
                nodes.append(body_node)
                node_map[body_node_id] = len(nodes) - 1
                connections.append((node_id, body_node_id, 'Has items'))
                
                current_y += 90
                
                # End loop (continue after loop)
                end_loop_id = f'{node_id}_end'
                end_loop_node = {
                    'id': end_loop_id,
                    'type': 'process',
                    'text': 'Continue',
                    'x': x_center,
                    'y': current_y,
                    'width': 120,
                    'height': 50
                }
                nodes.append(end_loop_node)
                node_map[end_loop_id] = len(nodes) - 1
                connections.append((node_id, end_loop_id, 'No items'))
                
                # Loop back arrow from body to decision
                connections.append((body_node_id, node_id, 'Loop back'))
                
                current_node_id = end_loop_id
                current_y += 90
                node_counter += 1
            
            elif flow_type == 'while':
                condition = flow.get('condition', 'condition')
                
                # Truncate long conditions
                if len(condition) > 40:
                    condition = condition[:37] + "..."
                
                # While decision node
                while_node = {
                    'id': node_id,
                    'type': 'decision',
                    'text': condition,
                    'x': x_center,
                    'y': current_y,
                    'width': max(160, len(condition) * 7),
                    'height': 70
                }
                nodes.append(while_node)
                node_map[node_id] = len(nodes) - 1
                
                # Connect previous node to while
                connections.append((current_node_id, node_id, None))
                
                current_y += 100
                
                # While body
                body_node_id = f'{node_id}_body'
                body_node = {
                    'id': body_node_id,
                    'type': 'process',
                    'text': 'While Body',
                    'x': x_center,
                    'y': current_y,
                    'width': 120,
                    'height': 50
                }
                nodes.append(body_node)
                node_map[body_node_id] = len(nodes) - 1
                connections.append((node_id, body_node_id, 'True'))
                
                current_y += 90
                
                # End while (continue after loop)
                end_while_id = f'{node_id}_end'
                end_while_node = {
                    'id': end_while_id,
                    'type': 'process',
                    'text': 'Continue',
                    'x': x_center,
                    'y': current_y,
                    'width': 120,
                    'height': 50
                }
                nodes.append(end_while_node)
                node_map[end_while_id] = len(nodes) - 1
                connections.append((node_id, end_while_id, 'False'))
                
                # Loop back arrow from body to decision
                connections.append((body_node_id, node_id, 'Loop back'))
                
                current_node_id = end_while_id
                current_y += 90
                node_counter += 1
            
            elif flow_type == 'return':
                # Return node
                return_node = {
                    'id': node_id,
                    'type': 'end',
                    'text': 'Return',
                    'x': x_center,
                    'y': current_y,
                    'width': 120,
                    'height': 50
                }
                nodes.append(return_node)
                node_map[node_id] = len(nodes) - 1
                connections.append((current_node_id, node_id, None))
                
                # End node
                end_node = {
                    'id': 'end',
                    'type': 'end',
                    'text': 'End',
                    'x': x_center,
                    'y': current_y + 90,
                    'width': 120,
                    'height': 50
                }
                nodes.append(end_node)
                node_map['end'] = len(nodes) - 1
                connections.append((node_id, 'end', None))
                break
        
        # Add end node if not already added
        if 'end' not in node_map:
            end_node = {
                'id': 'end',
                'type': 'end',
                'text': 'End',
                'x': x_center,
                'y': current_y,
                'width': 120,
                'height': 50
            }
            nodes.append(end_node)
            node_map['end'] = len(nodes) - 1
            connections.append((current_node_id, 'end', None))
        
        # Calculate SVG dimensions
        max_y = max(node['y'] for node in nodes) + 100
        max_x = max(abs(node['x'] - x_center) + node['width']//2 for node in nodes) * 2 + 100
        svg_width = max(600, max_x)
        svg_height = max(400, max_y)
        
        # Generate SVG
        svg = f'''<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <polygon points="0 0, 10 3, 0 6" fill="#333" />
    </marker>
  </defs>
  <style>
    .node-text {{ font-family: Arial, sans-serif; font-size: 11px; text-anchor: middle; dominant-baseline: middle; fill: #333; }}
    .label-text {{ font-family: Arial, sans-serif; font-size: 10px; fill: #666; }}
  </style>
'''
        
        # Draw connections first (so nodes appear on top)
        for from_id, to_id, label in connections:
            if from_id in node_map and to_id in node_map:
                from_node = nodes[node_map[from_id]]
                to_node = nodes[node_map[to_id]]
                
                # Calculate connection points based on node types
                if from_node['type'] == 'decision':
                    # From bottom of diamond
                    x1, y1 = from_node['x'], from_node['y'] + from_node['height'] // 2
                elif from_node['type'] == 'start':
                    # From bottom of oval
                    x1, y1 = from_node['x'], from_node['y'] + from_node['height'] // 2
                else:
                    # From bottom of rectangle
                    x1, y1 = from_node['x'], from_node['y'] + from_node['height'] // 2
                
                if to_node['type'] == 'decision':
                    # To top of diamond
                    x2, y2 = to_node['x'], to_node['y'] - to_node['height'] // 2
                elif to_node['type'] == 'end':
                    # To top of oval
                    x2, y2 = to_node['x'], to_node['y'] - to_node['height'] // 2
                else:
                    # To top of rectangle
                    x2, y2 = to_node['x'], to_node['y'] - to_node['height'] // 2
                
                # Special handling for loop back arrows
                if label == 'Loop back':
                    # Create curved path for loop back
                    mid_x = (x1 + x2) / 2
                    mid_y = min(y1, y2) - 40
                    svg += f'  <path d="M {x1} {y1} Q {mid_x} {mid_y} {x2} {y2}" stroke="#333" stroke-width="2" fill="none" marker-end="url(#arrowhead)" />\n'
                else:
                    # Straight line
                    svg += f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="2" marker-end="url(#arrowhead)" />\n'
                
                # Add label
                if label:
                    label_x = (x1 + x2) / 2
                    label_y = (y1 + y2) / 2
                    if label == 'Loop back':
                        label_y = mid_y - 10
                    svg += f'  <text x="{label_x}" y="{label_y}" class="label-text" text-anchor="middle">{label}</text>\n'
        
        # Draw nodes
        for node in nodes:
            x, y = node['x'], node['y']
            w, h = node['width'], node['height']
            text = node['text']
            node_type = node['type']
            
            # Word wrap text if too long
            words = text.split()
            if len(text) > 25:
                # Split into two lines
                mid = len(words) // 2
                line1 = ' '.join(words[:mid])
                line2 = ' '.join(words[mid:])
                text_lines = [line1, line2]
            else:
                text_lines = [text]
            
            if node_type == 'start' or node_type == 'end':
                # Oval shape
                rx, ry = w // 2, h // 2
                svg += f'  <ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="#e8f4f8" stroke="#2196F3" stroke-width="3" />\n'
                for i, line in enumerate(text_lines):
                    y_offset = (i - (len(text_lines) - 1) / 2) * 12
                    svg += f'  <text x="{x}" y="{y + y_offset}" class="node-text">{line}</text>\n'
            
            elif node_type == 'decision':
                # Diamond shape
                points = f"{x},{y-h//2} {x+w//2},{y} {x},{y+h//2} {x-w//2},{y}"
                svg += f'  <polygon points="{points}" fill="#fff4e6" stroke="#ff9800" stroke-width="2" />\n'
                for i, line in enumerate(text_lines):
                    y_offset = (i - (len(text_lines) - 1) / 2) * 12
                    svg += f'  <text x="{x}" y="{y + y_offset}" class="node-text">{line}</text>\n'
            
            else:
                # Rectangle
                svg += f'  <rect x="{x-w//2}" y="{y-h//2}" width="{w}" height="{h}" fill="#e8f5e9" stroke="#4caf50" stroke-width="2" rx="5" />\n'
                for i, line in enumerate(text_lines):
                    y_offset = (i - (len(text_lines) - 1) / 2) * 12
                    svg += f'  <text x="{x}" y="{y + y_offset}" class="node-text">{line}</text>\n'
        
        svg += '</svg>'
        return svg
    
    def _generate_empty_svg(self, message: str) -> str:
        """Generate an empty SVG with a message."""
        return f'''<svg width="400" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect width="400" height="200" fill="#f5f5f5" stroke="#ccc" stroke-width="2" rx="5" />
  <text x="200" y="100" font-family="Arial, sans-serif" font-size="14" text-anchor="middle" fill="#666">{message}</text>
</svg>'''
