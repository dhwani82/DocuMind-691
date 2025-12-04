"""Generate SVG flowcharts from parsed control flow."""
from typing import Dict, List, Any, Tuple, Optional
import math


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
        
        # Build flowchart structure with proper layout
        nodes = []
        edges = []
        node_map = {}
        
        # Layout constants
        NODE_SPACING_Y = 80
        BRANCH_SPACING_X = 200
        NODE_WIDTH = 150
        NODE_HEIGHT = 60
        DECISION_WIDTH = 120
        DECISION_HEIGHT = 80
        
        # Start node
        start_node = {
            'id': 'start',
            'type': 'start',
            'text': f'Start: {func_name}',
            'x': 400,
            'y': 50,
            'width': NODE_WIDTH,
            'height': NODE_HEIGHT
        }
        nodes.append(start_node)
        node_map['start'] = len(nodes) - 1
        
        current_y = 150
        current_node_id = 'start'
        node_counter = 1
        
        # Track branch positions for proper merging
        branch_stack = []
        
        # Process flow items
        for flow in flow_items:
            flow_type = flow.get('type')
            
            if flow_type == 'call':
                # Function call - show as action block
                action_label = flow.get('action_label', flow.get('call_label', 'Call function'))
                # Truncate long labels
                if len(action_label) > 30:
                    action_label = action_label[:27] + "..."
                
                call_id = f'call_{node_counter}'
                call_node = {
                    'id': call_id,
                    'type': 'process',
                    'text': action_label,
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(call_node)
                node_map[call_id] = len(nodes) - 1
                
                edges.append({
                    'from': current_node_id,
                    'to': call_id,
                    'label': None,
                    'type': 'straight'
                })
                
                current_node_id = call_id
                current_y += NODE_SPACING_Y
                node_counter += 1
            
            elif flow_type == 'with':
                # With statement - show enter, body, exit
                items = flow.get('items', [])
                if items:
                    with_label = items[0].get('label', 'Enter context')
                    context_name = with_label.replace('Enter ', '') if with_label.startswith('Enter ') else with_label
                else:
                    context_name = "context"
                    with_label = f"Enter {context_name}"
                
                # Truncate long labels
                if len(with_label) > 25:
                    with_label = with_label[:22] + "..."
                if len(context_name) > 20:
                    context_name = context_name[:17] + "..."
                
                enter_id = f'with_enter_{node_counter}'
                body_id = f'with_body_{node_counter}'
                exit_id = f'with_exit_{node_counter}'
                
                # Enter node
                enter_node = {
                    'id': enter_id,
                    'type': 'process',
                    'text': with_label,
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(enter_node)
                node_map[enter_id] = len(nodes) - 1
                edges.append({
                    'from': current_node_id,
                    'to': enter_id,
                    'label': None,
                    'type': 'straight'
                })
                
                current_y += NODE_SPACING_Y
                
                # Body node
                body_node = {
                    'id': body_id,
                    'type': 'process',
                    'text': 'With Body',
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(body_node)
                node_map[body_id] = len(nodes) - 1
                edges.append({
                    'from': enter_id,
                    'to': body_id,
                    'label': None,
                    'type': 'straight'
                })
                
                current_y += NODE_SPACING_Y
                
                # Exit node
                exit_node = {
                    'id': exit_id,
                    'type': 'process',
                    'text': f'Exit {context_name}',
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(exit_node)
                node_map[exit_id] = len(nodes) - 1
                edges.append({
                    'from': body_id,
                    'to': exit_id,
                    'label': None,
                    'type': 'straight'
                })
                
                current_node_id = exit_id
                current_y += NODE_SPACING_Y
                node_counter += 1
            
            elif flow_type == 'try':
                # Try/except block - show try, multiple except branches, finally
                try_id = f'try_{node_counter}'
                try_body_id = f'try_body_{node_counter}'
                exceptions = flow.get('exceptions', ['Exception'])
                has_finally = flow.get('has_finally', False)
                end_try_id = f'end_try_{node_counter}'
                
                # Try node
                try_node = {
                    'id': try_id,
                    'type': 'process',
                    'text': 'Try',
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(try_node)
                node_map[try_id] = len(nodes) - 1
                edges.append({
                    'from': current_node_id,
                    'to': try_id,
                    'label': None,
                    'type': 'straight'
                })
                
                current_y += NODE_SPACING_Y
                
                # Try body node
                try_body_node = {
                    'id': try_body_id,
                    'type': 'process',
                    'text': 'Try Body',
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(try_body_node)
                node_map[try_body_id] = len(nodes) - 1
                edges.append({
                    'from': try_id,
                    'to': try_body_id,
                    'label': None,
                    'type': 'straight'
                })
                
                # Add exception handlers
                except_nodes = []
                branch_x_offset = -BRANCH_SPACING_X * (len(exceptions) - 1) / 2
                
                for i, exc_type in enumerate(exceptions):
                    except_id = f'except_{i+1}_{node_counter}'
                    except_body_id = f'except_body_{i+1}_{node_counter}'
                    except_label = f'Except {exc_type}'
                    
                    # Truncate long exception names
                    if len(except_label) > 25:
                        except_label = except_label[:22] + "..."
                    
                    x_pos = 400 + branch_x_offset + i * BRANCH_SPACING_X
                    
                    # Exception handler node
                    except_node = {
                        'id': except_id,
                        'type': 'process',
                        'text': except_label,
                        'x': x_pos,
                        'y': current_y + NODE_SPACING_Y,
                        'width': NODE_WIDTH,
                        'height': NODE_HEIGHT
                    }
                    nodes.append(except_node)
                    node_map[except_id] = len(nodes) - 1
                    edges.append({
                        'from': try_body_id,
                        'to': except_id,
                        'label': exc_type,
                        'type': 'straight'
                    })
                    
                    # Exception body node
                    except_body_node = {
                        'id': except_body_id,
                        'type': 'process',
                        'text': f'{except_label} Body',
                        'x': x_pos,
                        'y': current_y + 2 * NODE_SPACING_Y,
                        'width': NODE_WIDTH,
                        'height': NODE_HEIGHT
                    }
                    nodes.append(except_body_node)
                    node_map[except_body_id] = len(nodes) - 1
                    edges.append({
                        'from': except_id,
                        'to': except_body_id,
                        'label': None,
                        'type': 'straight'
                    })
                    except_nodes.append(except_body_id)
                
                # Merge point after exceptions
                merge_y = current_y + 3 * NODE_SPACING_Y
                if has_finally:
                    finally_id = f'finally_{node_counter}'
                    finally_node = {
                        'id': finally_id,
                        'type': 'process',
                        'text': 'Finally',
                        'x': 400,
                        'y': merge_y,
                        'width': NODE_WIDTH,
                        'height': NODE_HEIGHT
                    }
                    nodes.append(finally_node)
                    node_map[finally_id] = len(nodes) - 1
                    
                    # Connect try body success path
                    edges.append({
                        'from': try_body_id,
                        'to': finally_id,
                        'label': 'Success',
                        'type': 'straight'
                    })
                    
                    # Connect all exception handlers to finally
                    for except_node in except_nodes:
                        edges.append({
                            'from': except_node,
                            'to': finally_id,
                            'label': None,
                            'type': 'straight'
                        })
                    
                    merge_y += NODE_SPACING_Y
                    end_try_node = {
                        'id': end_try_id,
                        'type': 'process',
                        'text': 'Continue',
                        'x': 400,
                        'y': merge_y,
                        'width': NODE_WIDTH,
                        'height': NODE_HEIGHT
                    }
                    nodes.append(end_try_node)
                    node_map[end_try_id] = len(nodes) - 1
                    edges.append({
                        'from': finally_id,
                        'to': end_try_id,
                        'label': None,
                        'type': 'straight'
                    })
                else:
                    # No finally, merge exception handlers
                    end_try_node = {
                        'id': end_try_id,
                        'type': 'process',
                        'text': 'Continue',
                        'x': 400,
                        'y': merge_y,
                        'width': NODE_WIDTH,
                        'height': NODE_HEIGHT
                    }
                    nodes.append(end_try_node)
                    node_map[end_try_id] = len(nodes) - 1
                    
                    # Connect try body success path
                    edges.append({
                        'from': try_body_id,
                        'to': end_try_id,
                        'label': 'Success',
                        'type': 'straight'
                    })
                    
                    # Connect all exception handlers
                    for except_node in except_nodes:
                        edges.append({
                            'from': except_node,
                            'to': end_try_id,
                            'label': None,
                            'type': 'straight'
                        })
                
                current_node_id = end_try_id
                current_y = merge_y + NODE_SPACING_Y
                node_counter += 1
            
            elif flow_type == 'if':
                condition = flow.get('condition', 'condition')
                has_else = flow.get('has_else', False)
                
                # Truncate long conditions
                if len(condition) > 30:
                    condition = condition[:27] + "..."
                
                # Decision node (diamond)
                decision_id = f'decision_{node_counter}'
                decision_node = {
                    'id': decision_id,
                    'type': 'decision',
                    'text': condition,
                    'x': 400,
                    'y': current_y,
                    'width': DECISION_WIDTH,
                    'height': DECISION_HEIGHT
                }
                nodes.append(decision_node)
                node_map[decision_id] = len(nodes) - 1
                
                # Connect previous node to decision
                edges.append({
                    'from': current_node_id,
                    'to': decision_id,
                    'label': None,
                    'type': 'straight'
                })
                
                current_y += NODE_SPACING_Y + DECISION_HEIGHT // 2
                
                # True branch
                true_id = f'{decision_id}_true'
                true_node = {
                    'id': true_id,
                    'type': 'process',
                    'text': 'If Body',
                    'x': 400 - (BRANCH_SPACING_X if has_else else 0),
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(true_node)
                node_map[true_id] = len(nodes) - 1
                
                edges.append({
                    'from': decision_id,
                    'to': true_id,
                    'label': 'Yes',
                    'type': 'straight',
                    'from_side': 'left' if has_else else 'bottom',
                    'to_side': 'top'
                })
                
                if has_else:
                    # False branch
                    false_id = f'{decision_id}_false'
                    false_node = {
                        'id': false_id,
                        'type': 'process',
                        'text': 'Else Body',
                        'x': 400 + BRANCH_SPACING_X,
                        'y': current_y,
                        'width': NODE_WIDTH,
                        'height': NODE_HEIGHT
                    }
                    nodes.append(false_node)
                    node_map[false_id] = len(nodes) - 1
                    
                    edges.append({
                        'from': decision_id,
                        'to': false_id,
                        'label': 'No',
                        'type': 'straight',
                        'from_side': 'right',
                        'to_side': 'top'
                    })
                    
                    current_y += NODE_SPACING_Y
                    
                    # Merge point
                    merge_id = f'{decision_id}_merge'
                    merge_node = {
                        'id': merge_id,
                        'type': 'process',
                        'text': 'Continue',
                        'x': 400,
                        'y': current_y,
                        'width': NODE_WIDTH,
                        'height': NODE_HEIGHT
                    }
                    nodes.append(merge_node)
                    node_map[merge_id] = len(nodes) - 1
                    
                    edges.append({
                        'from': true_id,
                        'to': merge_id,
                        'label': None,
                        'type': 'straight'
                    })
                    edges.append({
                        'from': false_id,
                        'to': merge_id,
                        'label': None,
                        'type': 'straight'
                    })
                    
                    current_node_id = merge_id
                else:
                    # No else - false goes directly to merge
                    current_y += NODE_SPACING_Y
                    merge_id = f'{decision_id}_merge'
                    merge_node = {
                        'id': merge_id,
                        'type': 'process',
                        'text': 'Continue',
                        'x': 400,
                        'y': current_y,
                        'width': NODE_WIDTH,
                        'height': NODE_HEIGHT
                    }
                    nodes.append(merge_node)
                    node_map[merge_id] = len(nodes) - 1
                    
                    edges.append({
                        'from': true_id,
                        'to': merge_id,
                        'label': None,
                        'type': 'straight'
                    })
                    edges.append({
                        'from': decision_id,
                        'to': merge_id,
                        'label': 'No',
                        'type': 'straight',
                        'from_side': 'bottom',
                        'to_side': 'top'
                    })
                    
                    current_node_id = merge_id
                
                current_y += NODE_SPACING_Y
                node_counter += 1
            
            elif flow_type == 'for':
                target = flow.get('target', 'item')
                iter_expr = flow.get('iter', 'iterable')
                
                # Truncate long expressions
                if len(iter_expr) > 25:
                    iter_expr = iter_expr[:22] + "..."
                
                loop_text = f'for {target} in {iter_expr}'
                
                # Loop decision node
                loop_id = f'loop_{node_counter}'
                loop_node = {
                    'id': loop_id,
                    'type': 'decision',
                    'text': loop_text,
                    'x': 400,
                    'y': current_y,
                    'width': DECISION_WIDTH,
                    'height': DECISION_HEIGHT
                }
                nodes.append(loop_node)
                node_map[loop_id] = len(nodes) - 1
                
                edges.append({
                    'from': current_node_id,
                    'to': loop_id,
                    'label': None,
                    'type': 'straight'
                })
                
                current_y += NODE_SPACING_Y + DECISION_HEIGHT // 2
                
                # Loop body
                body_id = f'{loop_id}_body'
                body_node = {
                    'id': body_id,
                    'type': 'process',
                    'text': 'Loop Body',
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(body_node)
                node_map[body_id] = len(nodes) - 1
                
                edges.append({
                    'from': loop_id,
                    'to': body_id,
                    'label': 'Has items',
                    'type': 'straight',
                    'from_side': 'bottom',
                    'to_side': 'top'
                })
                
                current_y += NODE_SPACING_Y
                
                # End loop (continue after loop)
                end_loop_id = f'{loop_id}_end'
                end_loop_node = {
                    'id': end_loop_id,
                    'type': 'process',
                    'text': 'Continue',
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(end_loop_node)
                node_map[end_loop_id] = len(nodes) - 1
                
                edges.append({
                    'from': loop_id,
                    'to': end_loop_id,
                    'label': 'No items',
                    'type': 'straight',
                    'from_side': 'right',
                    'to_side': 'top'
                })
                
                # Loop back arrow from body to decision
                edges.append({
                    'from': body_id,
                    'to': loop_id,
                    'label': 'Loop back',
                    'type': 'curved',
                    'curvature': -60
                })
                
                current_node_id = end_loop_id
                current_y += NODE_SPACING_Y
                node_counter += 1
            
            elif flow_type == 'while':
                condition = flow.get('condition', 'condition')
                
                # Truncate long conditions
                if len(condition) > 30:
                    condition = condition[:27] + "..."
                
                # While decision node
                while_id = f'while_{node_counter}'
                while_node = {
                    'id': while_id,
                    'type': 'decision',
                    'text': condition,
                    'x': 400,
                    'y': current_y,
                    'width': DECISION_WIDTH,
                    'height': DECISION_HEIGHT
                }
                nodes.append(while_node)
                node_map[while_id] = len(nodes) - 1
                
                edges.append({
                    'from': current_node_id,
                    'to': while_id,
                    'label': None,
                    'type': 'straight'
                })
                
                current_y += NODE_SPACING_Y + DECISION_HEIGHT // 2
                
                # While body
                body_id = f'{while_id}_body'
                body_node = {
                    'id': body_id,
                    'type': 'process',
                    'text': 'While Body',
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(body_node)
                node_map[body_id] = len(nodes) - 1
                
                edges.append({
                    'from': while_id,
                    'to': body_id,
                    'label': 'True',
                    'type': 'straight',
                    'from_side': 'bottom',
                    'to_side': 'top'
                })
                
                current_y += NODE_SPACING_Y
                
                # End while (continue after loop)
                end_while_id = f'{while_id}_end'
                end_while_node = {
                    'id': end_while_id,
                    'type': 'process',
                    'text': 'Continue',
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(end_while_node)
                node_map[end_while_id] = len(nodes) - 1
                
                edges.append({
                    'from': while_id,
                    'to': end_while_id,
                    'label': 'False',
                    'type': 'straight',
                    'from_side': 'right',
                    'to_side': 'top'
                })
                
                # Loop back arrow from body to decision
                edges.append({
                    'from': body_id,
                    'to': while_id,
                    'label': 'Loop back',
                    'type': 'curved',
                    'curvature': -60
                })
                
                current_node_id = end_while_id
                current_y += NODE_SPACING_Y
                node_counter += 1
            
            elif flow_type == 'return':
                # Return node
                return_id = f'return_{node_counter}'
                return_node = {
                    'id': return_id,
                    'type': 'end',
                    'text': 'Return',
                    'x': 400,
                    'y': current_y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(return_node)
                node_map[return_id] = len(nodes) - 1
                
                edges.append({
                    'from': current_node_id,
                    'to': return_id,
                    'label': None,
                    'type': 'straight'
                })
                
                # End node
                end_id = 'end'
                end_node = {
                    'id': end_id,
                    'type': 'end',
                    'text': 'End',
                    'x': 400,
                    'y': current_y + NODE_SPACING_Y,
                    'width': NODE_WIDTH,
                    'height': NODE_HEIGHT
                }
                nodes.append(end_node)
                node_map[end_id] = len(nodes) - 1
                
                edges.append({
                    'from': return_id,
                    'to': end_id,
                    'label': None,
                    'type': 'straight'
                })
                break
        
        # Add end node if not already added
        if 'end' not in node_map:
            end_id = 'end'
            end_node = {
                'id': end_id,
                'type': 'end',
                'text': 'End',
                'x': 400,
                'y': current_y,
                'width': NODE_WIDTH,
                'height': NODE_HEIGHT
            }
            nodes.append(end_node)
            node_map[end_id] = len(nodes) - 1
            
            edges.append({
                'from': current_node_id,
                'to': end_id,
                'label': None,
                'type': 'straight'
            })
        
        # Calculate SVG dimensions
        max_y = max(node['y'] for node in nodes) + 100
        max_x = max(abs(node['x'] - 400) + node['width']//2 for node in nodes) * 2 + 200
        svg_width = max(800, max_x)
        svg_height = max(500, max_y)
        
        # Generate SVG
        svg = self._generate_svg_content(nodes, edges, node_map, svg_width, svg_height)
        return svg
    
    def _get_node_connection_point(self, node: Dict, side: str = 'bottom') -> Tuple[float, float]:
        """Get connection point coordinates for a node based on side."""
        x, y = node['x'], node['y']
        w, h = node['width'], node['height']
        node_type = node['type']
        
        if node_type == 'decision':
            # Diamond shape
            if side == 'top':
                return (x, y - h // 2)
            elif side == 'bottom':
                return (x, y + h // 2)
            elif side == 'left':
                return (x - w // 2, y)
            elif side == 'right':
                return (x + w // 2, y)
            else:
                return (x, y + h // 2)
        else:
            # Rectangle or oval
            if side == 'top':
                return (x, y - h // 2)
            elif side == 'bottom':
                return (x, y + h // 2)
            elif side == 'left':
                return (x - w // 2, y)
            elif side == 'right':
                return (x + w // 2, y)
            else:
                return (x, y + h // 2)
    
    def _generate_svg_content(self, nodes: List[Dict], edges: List[Dict], node_map: Dict, width: int, height: int) -> str:
        """Generate the actual SVG content."""
        svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <polygon points="0 0, 10 3, 0 6" fill="#ffffff" stroke="#333" stroke-width="0.5" />
    </marker>
  </defs>
  <style>
    .node-text {{ font-family: Arial, sans-serif; font-size: 12px; text-anchor: middle; dominant-baseline: middle; fill: #333; font-weight: 500; }}
    .edge-label {{ font-family: Arial, sans-serif; font-size: 11px; fill: #666; text-anchor: middle; }}
  </style>
'''
        
        # Draw edges first (so nodes appear on top)
        for edge in edges:
            from_id = edge['from']
            to_id = edge['to']
            
            if from_id not in node_map or to_id not in node_map:
                continue
            
            from_node = nodes[node_map[from_id]]
            to_node = nodes[node_map[to_id]]
            
            # Get connection points
            from_side = edge.get('from_side', 'bottom')
            to_side = edge.get('to_side', 'top')
            
            x1, y1 = self._get_node_connection_point(from_node, from_side)
            x2, y2 = self._get_node_connection_point(to_node, to_side)
            
            # Draw edge
            if edge['type'] == 'curved':
                # Curved path for loop back
                curvature = edge.get('curvature', -50)
                mid_x = (x1 + x2) / 2
                mid_y = min(y1, y2) + curvature
                
                path_d = f"M {x1} {y1} Q {mid_x} {mid_y} {x2} {y2}"
                svg += f'  <path d="{path_d}" stroke="#333" stroke-width="2" fill="none" marker-end="url(#arrowhead)" />\n'
                
                # Label for curved edge
                if edge.get('label'):
                    label_x = mid_x
                    label_y = mid_y - 10
                    svg += f'  <text x="{label_x}" y="{label_y}" class="edge-label">{edge["label"]}</text>\n'
            else:
                # Straight line
                svg += f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="2" marker-end="url(#arrowhead)" />\n'
                
                # Label for straight edge
                if edge.get('label'):
                    label_x = (x1 + x2) / 2
                    label_y = (y1 + y2) / 2 - 5
                    svg += f'  <text x="{label_x}" y="{label_y}" class="edge-label">{edge["label"]}</text>\n'
        
        # Draw nodes
        for node in nodes:
            x, y = node['x'], node['y']
            w, h = node['width'], node['height']
            text = node['text']
            node_type = node['type']
            
            # Word wrap text
            words = text.split()
            if len(text) > 20:
                mid = len(words) // 2
                line1 = ' '.join(words[:mid])
                line2 = ' '.join(words[mid:])
                text_lines = [line1, line2]
            else:
                text_lines = [text]
            
            if node_type == 'start' or node_type == 'end':
                # Oval shape
                rx, ry = w // 2, h // 2
                fill_color = "#e8f4f8" if node_type == 'start' else "#ffebee"
                stroke_color = "#2196F3" if node_type == 'start' else "#f44336"
                stroke_width = "3" if node_type == 'start' else "2"
                
                svg += f'  <ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" />\n'
                
                for i, line in enumerate(text_lines):
                    y_offset = (i - (len(text_lines) - 1) / 2) * 14
                    svg += f'  <text x="{x}" y="{y + y_offset}" class="node-text">{line}</text>\n'
            
            elif node_type == 'decision':
                # Diamond shape
                points = f"{x},{y-h//2} {x+w//2},{y} {x},{y+h//2} {x-w//2},{y}"
                svg += f'  <polygon points="{points}" fill="#fff4e6" stroke="#ff9800" stroke-width="2" />\n'
                
                for i, line in enumerate(text_lines):
                    y_offset = (i - (len(text_lines) - 1) / 2) * 14
                    svg += f'  <text x="{x}" y="{y + y_offset}" class="node-text">{line}</text>\n'
            
            else:
                # Rectangle (process node)
                svg += f'  <rect x="{x-w//2}" y="{y-h//2}" width="{w}" height="{h}" fill="#e8f5e9" stroke="#4caf50" stroke-width="2" rx="5" />\n'
                
                for i, line in enumerate(text_lines):
                    y_offset = (i - (len(text_lines) - 1) / 2) * 14
                    svg += f'  <text x="{x}" y="{y + y_offset}" class="node-text">{line}</text>\n'
        
        svg += '</svg>'
        return svg
    
    def _generate_empty_svg(self, message: str) -> str:
        """Generate an empty SVG with a message."""
        return f'''<svg width="400" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect width="400" height="200" fill="#f5f5f5" stroke="#ccc" stroke-width="2" rx="5" />
  <text x="200" y="100" font-family="Arial, sans-serif" font-size="14" text-anchor="middle" fill="#666">{message}</text>
</svg>'''
