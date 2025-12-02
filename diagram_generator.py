"""Generate Mermaid diagrams from parsed code relationships."""
from typing import Dict, List, Any, Set


class DiagramGenerator:
    """Generate Mermaid diagrams based on parsed code relationships."""
    
    def __init__(self, parse_result: Dict[str, Any]):
        """Initialize with parse results.
        
        Args:
            parse_result: Result from CodeParser.parse()
        """
        self.parse_result = parse_result
        self.classes = parse_result.get('classes', [])
        self.functions = parse_result.get('functions', [])
        self.function_calls = parse_result.get('function_calls', [])
        self.method_calls = parse_result.get('method_calls', [])
        self.class_instantiations = parse_result.get('class_instantiations', [])
        self.imports = parse_result.get('imports', [])
        self.control_flow = parse_result.get('control_flow', [])
    
    def generate_architecture_diagram(self) -> str:
        """Generate Mermaid class diagram showing class relationships.
        
        Returns:
            Mermaid diagram code as string
        """
        if not self.classes:
            return "```mermaid\ngraph TD\n    A[\"📦 No Classes Found\"] --> B[\"Add classes to your code\"]\n    style A fill:#e8f4f8\n    style B fill:#fff4e6\n```"
        
        lines = ["```mermaid", "classDiagram"]
        lines.append("    direction TB")
        
        # Add classes with better formatting
        for cls in self.classes:
            class_name = cls['name']
            lines.append(f"    class {class_name} {{")
            
            # Add class variables (limit to 3 for readability)
            class_vars = cls.get('class_variables', [])[:3]
            if class_vars:
                for var in class_vars:
                    var_name = var['name']
                    lines.append(f"        +{var_name}")
                if len(cls.get('class_variables', [])) > 3:
                    lines.append(f"        +... ({len(cls.get('class_variables', [])) - 3} more)")
            
            # Add methods (limit to 4 for readability)
            methods = cls.get('methods', [])[:4]
            if methods:
                for method in methods:
                    method_name = method['name']
                    method_type = "🔁 " if method.get('is_async') else ""
                    lines.append(f"        {method_type}{method_name}()")
                if len(cls.get('methods', [])) > 4:
                    lines.append(f"        +... ({len(cls.get('methods', [])) - 4} more methods)")
            
            lines.append("    }")
        
        # Add inheritance relationships with clear labels
        inheritance_count = 0
        for cls in self.classes:
            if cls.get('bases'):
                for base in cls['bases']:
                    base_name = base.split('.')[-1]
                    if any(c['name'] == base_name for c in self.classes):
                        lines.append(f"    {base_name} <|-- {cls['name']} : inherits")
                        inheritance_count += 1
        
        # Add instantiation relationships (who creates instances of which class)
        instantiation_map = {}
        for inst in self.class_instantiations:
            caller = inst['caller']
            class_name = inst['class_name']
            if class_name not in instantiation_map:
                instantiation_map[class_name] = set()
            instantiation_map[class_name].add(caller)
        
        for class_name, callers in instantiation_map.items():
            for caller in callers:
                if '.' in caller:
                    caller_class = caller.split('.')[0]
                    if any(c['name'] == caller_class for c in self.classes):
                        lines.append(f"    {caller_class} ..> {class_name} : \"creates\"")
        
        # Add method call relationships between classes (simplified)
        method_call_map = {}
        for method_call in self.method_calls:
            caller = method_call['caller']
            target_class = method_call['class_name']
            method = method_call['method']
            
            if '.' in caller:
                caller_class = caller.split('.')[0]
                if caller_class != target_class:
                    key = (caller_class, target_class)
                    if key not in method_call_map:
                        method_call_map[key] = set()
                    method_call_map[key].add(method)
        
        # Limit relationships to avoid clutter
        relationship_count = 0
        for (caller_class, target_class), methods in method_call_map.items():
            if relationship_count >= 5:  # Limit to 5 relationships
                break
            if any(c['name'] == caller_class for c in self.classes) and \
               any(c['name'] == target_class for c in self.classes):
                methods_list = list(methods)[:2]  # Limit to 2 methods
                if len(methods_list) == 1:
                    lines.append(f"    {caller_class} --> {target_class} : \"calls {methods_list[0]}()\"")
                else:
                    lines.append(f"    {caller_class} --> {target_class} : \"calls methods\"")
                relationship_count += 1
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_sequence_diagram(self) -> str:
        """Generate Mermaid sequence diagram showing function call sequences.
        
        Returns:
            Mermaid diagram code as string
        """
        if not self.function_calls and not self.method_calls:
            return "```mermaid\nsequenceDiagram\n    participant Main as \"📋 Main\"\n    Main->>Main: \"No function calls detected\"\n    Note over Main: Add function calls to see interactions\n```"
        
        lines = ["```mermaid", "sequenceDiagram"]
        lines.append("    autonumber")
        
        # Collect all participants with their types
        participants = {}  # name -> type (class/function)
        
        # Add top-level functions as participants
        top_level_funcs = [f for f in self.functions if not f.get('is_nested', False)]
        for func in top_level_funcs:
            participants[func['name']] = 'function'
        
        # Add classes as participants
        for cls in self.classes:
            participants[cls['name']] = 'class'
        
        # Add callers and callees from function calls
        for call in self.function_calls:
            caller = call['caller']
            callee = call['callee']
            
            # Extract class/function name from caller
            if '.' in caller:
                caller_name = caller.split('.')[0]
                if caller_name not in participants:
                    participants[caller_name] = 'class' if any(c['name'] == caller_name for c in self.classes) else 'function'
            else:
                if caller not in participants:
                    participants[caller] = 'function'
            
            # Extract class/function name from callee
            if '.' in callee:
                callee_parts = callee.split('.')
                if len(callee_parts) >= 2:
                    callee_name = callee_parts[0]
                    if callee_name not in participants:
                        participants[callee_name] = 'class' if any(c['name'] == callee_name for c in self.classes) else 'function'
            else:
                if callee not in participants:
                    participants[callee] = 'function'
        
        # Add participants with descriptive labels
        participant_list = sorted(list(participants.keys()))
        participant_map = {}  # short name -> full name for diagram
        
        # Create better short names (like M, SD, PC in the example)
        used_short_names = set()
        
        for i, participant in enumerate(participant_list[:12]):  # Limit to 12 participants
            # Create short alias - try to use meaningful abbreviations
            short_name = None
            
            # Try common abbreviations first
            abbrev_map = {
                'main': 'M', 'run': 'R', 'start': 'S',
                'cart': 'CART', 'product': 'PC', 'catalog': 'CAT',
                'phone': 'P', 'laptop': 'L', 'device': 'D',
                'log': 'LOG', 'tax': 'TAX', 'email': 'E',
                'shopping': 'SD', 'demo': 'DEM'
            }
            
            participant_lower = participant.lower()
            for key, abbrev in abbrev_map.items():
                if key in participant_lower:
                    short_name = abbrev
                    break
            
            # If no abbreviation found, create one
            if not short_name:
                # Use first letters of words or first 3-4 chars
                words = participant.replace('_', ' ').split()
                if len(words) > 1:
                    short_name = ''.join([w[0].upper() for w in words[:3]])
                else:
                    short_name = participant[:4].upper()
            
            # Ensure uniqueness
            original_short = short_name
            counter = 1
            while short_name in used_short_names:
                short_name = f"{original_short}{counter}"
                counter += 1
            
            used_short_names.add(short_name)
            participant_map[participant] = short_name
            
            # Create descriptive label
            p_type = participants[participant]
            if p_type == 'class':
                label = f"{participant}"
            else:
                # For functions, show with parentheses
                label = f"{participant}()"
            
            lines.append(f"    participant {short_name} as \"{label}\"")
        
        # Build comprehensive call sequence with context
        all_calls = []
        
        # Process function calls
        for call in self.function_calls:
            caller = call['caller']
            callee = call['callee']
            line = call['line']
            
            # Extract participant names
            if '.' in caller:
                caller_participant = caller.split('.')[0]
                caller_method = '.'.join(caller.split('.')[1:])
            else:
                caller_participant = caller
                caller_method = None
            
            if '.' in callee:
                callee_parts = callee.split('.')
                if len(callee_parts) >= 2:
                    callee_participant = callee_parts[0]
                    callee_method = callee_parts[1]
                else:
                    callee_participant = callee
                    callee_method = callee
            else:
                callee_participant = callee
                callee_method = callee
            
            # Only include if both participants are in our list
            if caller_participant in participant_list and callee_participant in participant_list:
                all_calls.append({
                    'caller': caller_participant,
                    'target': callee_participant,
                    'method': callee_method,
                    'line': line,
                    'type': 'function_call'
                })
        
        # Process method calls
        for method_call in self.method_calls:
            caller = method_call['caller']
            target_class = method_call['class_name']
            method = method_call['method']
            line = method_call['line']
            
            if '.' in caller:
                caller_participant = caller.split('.')[0]
            else:
                caller_participant = caller
            
            if caller_participant in participant_list and target_class in participant_list:
                all_calls.append({
                    'caller': caller_participant,
                    'target': target_class,
                    'method': method,
                    'line': line,
                    'type': 'method_call'
                })
        
        # Sort all calls by line number to show execution order
        all_calls.sort(key=lambda x: x['line'])
        
        # Group calls to identify loops and patterns
        call_groups = {}
        for call in all_calls[:30]:  # Limit to 30 calls
            caller = call['caller']
            if caller not in call_groups:
                call_groups[caller] = []
            call_groups[caller].append(call)
        
        # Generate sequence diagram with detailed interactions
        processed_calls = set()
        call_count = 0
        
        # Start with main/entry point
        main_participant = None
        if participant_list:
            # Find a likely main function or first function
            for p in participant_list:
                if 'main' in p.lower() or p.lower() in ['main', 'run', 'start']:
                    main_participant = p
                    break
            if not main_participant:
                main_participant = participant_list[0]
        
        # Find loop patterns first
        call_patterns = {}
        for call in all_calls:
            pattern = (call['caller'], call['target'], call['method'])
            if pattern not in call_patterns:
                call_patterns[pattern] = []
            call_patterns[pattern].append(call)
        
        # Identify loops (patterns that repeat 3+ times)
        loop_patterns = {pattern: calls for pattern, calls in call_patterns.items() if len(calls) >= 3}
        loop_processed = set()
        
        # Generate sequence in execution order with loops
        i = 0
        while i < len(all_calls) and call_count < 30:
            call = all_calls[i]
            pattern = (call['caller'], call['target'], call['method'])
            
            # Check if this pattern is a loop and hasn't been processed
            if pattern in loop_patterns and pattern not in loop_processed:
                # Process as a loop
                caller = call['caller']
                target = call['target']
                method = call['method']
                caller_short = participant_map.get(caller, caller)
                target_short = participant_map.get(target, target)
                
                # Determine loop description based on context
                loop_desc = "Each item"
                if participants.get(target) == 'class':
                    # Try to make it more descriptive
                    if 'product' in target.lower() or 'item' in target.lower():
                        loop_desc = "Each item in catalog"
                    elif 'device' in target.lower():
                        loop_desc = "Each device"
                    else:
                        loop_desc = f"Each {target.lower()}"
                elif 'for' in method.lower() or 'each' in method.lower() or 'loop' in method.lower():
                    loop_desc = "Each iteration"
                elif 'list' in method.lower() or 'items' in method.lower():
                    loop_desc = "Each item in list"
                
                # Add loop block
                lines.append(f"    loop \"{loop_desc}\"")
                
                # Add calls within loop (show representative iterations)
                loop_calls = sorted(loop_patterns[pattern], key=lambda x: x['line'])
                iterations_shown = min(3, len(loop_calls))  # Show up to 3 iterations
                
                for j in range(iterations_shown):
                    if call_count >= 25:
                        break
                    lines.append(f"        {caller_short}->>{target_short}: \"{method}()\"")
                    
                    # Add return arrow with descriptive response
                    if participants.get(target) == 'class':
                        # Try to determine return type
                        if 'detail' in method.lower():
                            lines.append(f"        {target_short}-->>{caller_short}: \"specs()\"")
                        elif 'get' in method.lower() or 'fetch' in method.lower():
                            lines.append(f"        {target_short}-->>{caller_short}: \"data\"")
                        else:
                            lines.append(f"        {target_short}-->>{caller_short}: \"result\"")
                    else:
                        lines.append(f"        {target_short}-->>{caller_short}: \"return value\"")
                    
                    call_count += 1
                
                lines.append(f"    end")
                loop_processed.add(pattern)
                
                # Skip the individual calls that were in the loop
                skip_count = len(loop_patterns[pattern])
                i += skip_count
                continue
            
            # Regular call (not in a processed loop)
            if pattern not in loop_processed:
                caller = call['caller']
                target = call['target']
                method = call['method']
                
                # Skip self-calls unless they're method calls
                if caller == target and call['type'] != 'method_call':
                    i += 1
                    continue
                
                caller_short = participant_map.get(caller, caller)
                target_short = participant_map.get(target, target)
                
                # Create descriptive message with context
                if call['type'] == 'method_call':
                    message = f"{method}()"
                    # Add parameters if it's a constructor or important method
                    if method == '__init__' or 'new' in method.lower():
                        # Try to get class name for constructor
                        if participants.get(target) == 'class':
                            message = f"new {target}()"
                elif method and method != target:
                    message = f"{method}()"
                else:
                    message = f"{target}()"
                
                # Add call
                lines.append(f"    {caller_short}->>{target_short}: \"{message}\"")
                
                # Add return arrow with descriptive response
                if call['type'] == 'method_call' and participants.get(target) == 'class':
                    # Determine return type based on method name
                    method_lower = method.lower()
                    if 'detail' in method_lower or 'spec' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"specs()\"")
                    elif 'get' in method_lower or 'fetch' in method_lower or 'return' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"data\"")
                    elif 'valid' in method_lower or 'check' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"true\"")
                    elif 'sum' in method_lower or 'total' in method_lower or 'calculate' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"final_price\"")
                    elif 'new' in method_lower or '__init__' in method_lower:
                        lines.append(f"    {target_short}-->>{caller_short}: \"instance\"")
                    else:
                        lines.append(f"    {target_short}-->>{caller_short}: \"result\"")
                elif participants.get(target) == 'function':
                    # For function calls, show return
                    func_name = target.lower()
                    if 'catalog' in func_name or 'list' in func_name:
                        lines.append(f"    {target_short}-->>{caller_short}: \"[Device List]\"")
                    elif 'valid' in func_name or 'check' in func_name:
                        lines.append(f"    {target_short}-->>{caller_short}: \"true\"")
                    else:
                        lines.append(f"    {target_short}-->>{caller_short}: \"return value\"")
                
                call_count += 1
                loop_processed.add(pattern)
            
            i += 1
        
        # Add final return if main function exists
        if main_participant and call_count > 0:
            main_short = participant_map.get(main_participant, main_participant)
            # Check if main called something that should return
            for call in all_calls:
                if call['caller'] == main_participant:
                    target_short = participant_map.get(call['target'], call['target'])
                    if participants.get(call['target']) == 'function':
                        lines.append(f"    {target_short}-->>{main_short}: \"return\"")
                    break
        
        # If no calls were added, show a message
        if call_count == 0:
            if main_participant:
                main_short = participant_map.get(main_participant, main_participant)
                lines.append(f"    {main_short}->>{main_short}: \"No interactions detected\"")
                lines.append(f"    Note over {main_short}: Add function/method calls to see sequence")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_dependency_diagram(self) -> str:
        """Generate Mermaid dependency diagram showing module/import relationships.
        
        Returns:
            Mermaid diagram code as string
        """
        if not self.imports:
            return "```mermaid\ngraph TD\n    A[\"📦 No Imports Found\"] --> B[\"Add imports to your code\"]\n    style A fill:#e8f4f8\n    style B fill:#fff4e6\n```"
        
        lines = ["```mermaid", "graph TD"]
        lines.append("    direction TB")
        
        # Group imports by module
        modules = set()
        import_details = {}
        for imp in self.imports:
            if imp['type'] == 'import':
                module = imp['module'].split('.')[0]
                modules.add(module)
                if module not in import_details:
                    import_details[module] = []
                import_details[module].append(imp['module'])
            elif imp['type'] == 'from_import' and imp['module']:
                module = imp['module'].split('.')[0]
                modules.add(module)
                if module not in import_details:
                    import_details[module] = []
                import_details[module].append(f"{imp['module']}.{imp['name']}")
        
        # Current module (your code)
        current_module = "CurrentModule"
        lines.append(f"    {current_module}[\"📄 Your Code\"]")
        lines.append(f"    style {current_module} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        
        # Add modules as nodes with better labels
        module_list = sorted(list(modules))[:12]  # Limit to 12 for readability
        for module in module_list:
            module_id = module.replace('.', '_').replace('-', '_')
            count = len(import_details.get(module, []))
            label = f"📚 {module}" if count > 1 else f"📦 {module}"
            lines.append(f"    {module_id}[\"{label}\"]")
            lines.append(f"    style {module_id} fill:#fff4e6,stroke:#ff9800")
            lines.append(f"    {current_module} -->|imports| {module_id}")
        
        if len(modules) > 12:
            lines.append(f"    More[\"... and {len(modules) - 12} more modules\"]")
            lines.append(f"    style More fill:#f5f5f5,stroke:#999")
            lines.append(f"    {current_module} --> More")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_flowchart(self, function_name: str = None) -> str:
        """Generate Mermaid flowchart for a specific function or all functions.
        
        Args:
            function_name: Name of function to generate flowchart for. If None, generates for first function with control flow.
            
        Returns:
            Mermaid flowchart code as string
        """
        # Get functions to process
        if function_name:
            funcs_to_process = [f for f in self.functions if f['name'] == function_name]
        else:
            # Get top-level functions (not nested, not methods)
            funcs_to_process = [f for f in self.functions if not f.get('is_nested', False)]
        
        if not funcs_to_process:
            return "```mermaid\nflowchart TD\n    A[No functions found] --> B[Add functions to generate flowchart]\n```"
        
        # Find function with most control flow
        funcs_with_flow = []
        for func in funcs_to_process:
            func_name = func['name']
            func_flow = [cf for cf in self.control_flow if cf.get('function') == func_name]
            if func_flow:
                funcs_with_flow.append((func, len(func_flow)))
        
        if funcs_with_flow:
            # Sort by control flow count and take the first
            funcs_with_flow.sort(key=lambda x: x[1], reverse=True)
            return self._generate_single_flowchart(funcs_with_flow[0][0])
        else:
            # No control flow found, show simple message
            return "```mermaid\nflowchart TD\n    A[Functions found] --> B[No control flow structures detected]\n    B --> C[Add if/else, loops, etc. to see flowcharts]\n```"
    
    def _generate_single_flowchart(self, func_info: Dict) -> str:
        """Generate flowchart for a single function."""
        func_name = func_info['name']
        lines = ["```mermaid", "flowchart TD"]
        
        # Get control flow for this function
        func_flow = [cf for cf in self.control_flow if cf.get('function') == func_name]
        
        # Start node with better label
        start_id = "Start"
        lines.append(f"    {start_id}([\"▶️ Start: {func_name}\"])")
        lines.append(f"    style {start_id} fill:#e8f4f8,stroke:#2196F3,stroke-width:3px")
        
        # Process control flow structures
        node_id = 1
        current_node = start_id
        
        for flow in sorted(func_flow, key=lambda x: x.get('line', 0)):
            flow_type = flow.get('type')
            
            if flow_type == 'if':
                condition = flow.get('condition', 'condition')
                # Truncate long conditions
                if len(condition) > 30:
                    condition = condition[:27] + "..."
                if_id = f"IF{node_id}"
                true_id = f"TRUE{node_id}"
                false_id = f"FALSE{node_id}"
                end_if_id = f"ENDIF{node_id}"
                
                lines.append(f"    {current_node} --> {if_id}{{\"{condition}\"}}")
                lines.append(f"    style {if_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
                lines.append(f"    {if_id} -->|\"✅ True\"| {true_id}[\"📝 If Body\"]")
                lines.append(f"    style {true_id} fill:#e8f5e9,stroke:#4caf50")
                
                if flow.get('has_else'):
                    lines.append(f"    {if_id} -->|\"❌ False\"| {false_id}[\"📝 Else Body\"]")
                    lines.append(f"    style {false_id} fill:#e8f5e9,stroke:#4caf50")
                    lines.append(f"    {true_id} --> {end_if_id}[\"➡️ Continue\"]")
                    lines.append(f"    {false_id} --> {end_if_id}")
                else:
                    lines.append(f"    {if_id} -->|\"❌ False\"| {end_if_id}[\"➡️ Continue\"]")
                    lines.append(f"    {true_id} --> {end_if_id}")
                
                lines.append(f"    style {end_if_id} fill:#f3e5f5,stroke:#9c27b0")
                current_node = end_if_id
                node_id += 1
            
            elif flow_type == 'for':
                target = flow.get('target', 'item')
                iter_expr = flow.get('iter', 'iterable')
                # Truncate long expressions
                if len(iter_expr) > 25:
                    iter_expr = iter_expr[:22] + "..."
                loop_id = f"LOOP{node_id}"
                body_id = f"BODY{node_id}"
                end_loop_id = f"ENDLOOP{node_id}"
                
                lines.append(f"    {current_node} --> {loop_id}{{\"🔄 for {target} in {iter_expr}\"}}")
                lines.append(f"    style {loop_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
                lines.append(f"    {loop_id} -->|\"✅ Has items\"| {body_id}[\"📝 Loop Body\"]")
                lines.append(f"    style {body_id} fill:#e8f5e9,stroke:#4caf50")
                lines.append(f"    {loop_id} -->|\"❌ No items\"| {end_loop_id}[\"➡️ Continue\"]")
                lines.append(f"    {body_id} -->|\"↩️ Loop back\"| {loop_id}")
                lines.append(f"    style {end_loop_id} fill:#f3e5f5,stroke:#9c27b0")
                
                current_node = end_loop_id
                node_id += 1
            
            elif flow_type == 'while':
                condition = flow.get('condition', 'condition')
                # Truncate long conditions
                if len(condition) > 30:
                    condition = condition[:27] + "..."
                loop_id = f"WHILE{node_id}"
                body_id = f"BODY{node_id}"
                end_while_id = f"ENDWHILE{node_id}"
                
                lines.append(f"    {current_node} --> {loop_id}{{\"🔄 {condition}\"}}")
                lines.append(f"    style {loop_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
                lines.append(f"    {loop_id} -->|\"✅ True\"| {body_id}[\"📝 While Body\"]")
                lines.append(f"    style {body_id} fill:#e8f5e9,stroke:#4caf50")
                lines.append(f"    {loop_id} -->|\"❌ False\"| {end_while_id}[\"➡️ Continue\"]")
                lines.append(f"    {body_id} -->|\"↩️ Loop back\"| {loop_id}")
                lines.append(f"    style {end_while_id} fill:#f3e5f5,stroke:#9c27b0")
                
                current_node = end_while_id
                node_id += 1
            
            elif flow_type == 'return':
                return_id = f"RETURN{node_id}"
                if flow.get('has_value'):
                    lines.append(f"    {current_node} --> {return_id}([\"↩️ Return with value\"])")
                else:
                    lines.append(f"    {current_node} --> {return_id}([\"↩️ Return\"])")
                lines.append(f"    style {return_id} fill:#ffebee,stroke:#f44336,stroke-width:2px")
                lines.append(f"    {return_id} --> END([\"🏁 End\"])")
                lines.append(f"    style END fill:#e8f4f8,stroke:#2196F3,stroke-width:3px")
                current_node = None
                node_id += 1
                break
            
            elif flow_type == 'break':
                break_id = f"BREAK{node_id}"
                lines.append(f"    {current_node} --> {break_id}([Break])")
                lines.append(f"    {break_id} --> END([End])")
                current_node = None
                node_id += 1
                break
            
            elif flow_type == 'continue':
                continue_id = f"CONTINUE{node_id}"
                lines.append(f"    {current_node} --> {continue_id}([Continue])")
                # Continue goes back to loop start - simplified for now
                current_node = continue_id
                node_id += 1
        
        # End node
        if current_node:
            lines.append(f"    {current_node} --> END([\"🏁 End\"])")
            lines.append(f"    style END fill:#e8f4f8,stroke:#2196F3,stroke-width:3px")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_structure_diagram(self) -> str:
        """Generate Mermaid structure diagram showing hierarchical code organization.
        
        Shows the overall structure: classes with methods, top-level functions,
        nested functions, and their relationships.
        
        Returns:
            Mermaid diagram code as string
        """
        if not self.classes and not self.functions:
            return "```mermaid\ngraph TD\n    A[\"📦 No Code Structure Found\"] --> B[\"Add classes or functions to your code\"]\n    style A fill:#e8f4f8\n    style B fill:#fff4e6\n```"
        
        lines = ["```mermaid", "graph TD"]
        lines.append("    direction TB")
        
        # Root node
        root_id = "ROOT"
        lines.append(f"    {root_id}[\"📄 Code Structure\"]")
        lines.append(f"    style {root_id} fill:#e8f5e9,stroke:#4caf50,stroke-width:3px")
        
        # Separate top-level functions and nested functions
        top_level_funcs = [f for f in self.functions if not f.get('is_nested', False)]
        nested_funcs = [f for f in self.functions if f.get('is_nested', False)]
        
        # Group functions by their parent (if nested)
        nested_by_parent = {}
        for func in nested_funcs:
            # Try to find parent - this is simplified, actual parent tracking would need parser enhancement
            parent = "Nested"
            nested_by_parent.setdefault(parent, []).append(func)
        
        # Add classes section
        if self.classes:
            classes_id = "CLASSES"
            lines.append(f"    {root_id} --> {classes_id}[\"🏛️ Classes ({len(self.classes)})\"]")
            lines.append(f"    style {classes_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
            
            for cls in self.classes:
                class_id = f"CLASS_{cls['name']}".replace(' ', '_')
                class_label = f"📦 {cls['name']}"
                
                # Add inheritance info
                if cls.get('bases'):
                    bases_str = ', '.join(cls['bases'][:2])
                    if len(cls['bases']) > 2:
                        bases_str += f" +{len(cls['bases']) - 2}"
                    class_label += f"\\n(extends {bases_str})"
                
                lines.append(f"    {classes_id} --> {class_id}[\"{class_label}\"]")
                lines.append(f"    style {class_id} fill:#e3f2fd,stroke:#2196F3")
                
                # Add methods
                methods = cls.get('methods', [])
                if methods:
                    methods_id = f"{class_id}_METHODS"
                    lines.append(f"    {class_id} --> {methods_id}[\"🔧 Methods ({len(methods)})\"]")
                    lines.append(f"    style {methods_id} fill:#f3e5f5,stroke:#9c27b0")
                    
                    # Show first 5 methods
                    for method in methods[:5]:
                        method_id = f"{class_id}_M_{method['name']}".replace(' ', '_')
                        method_label = method['name']
                        if method.get('is_async'):
                            method_label = f"🔁 {method_label}"
                        method_label += "()"
                        lines.append(f"    {methods_id} --> {method_id}[\"{method_label}\"]")
                        lines.append(f"    style {method_id} fill:#fce4ec,stroke:#e91e63")
                    
                    if len(methods) > 5:
                        more_id = f"{class_id}_MORE"
                        lines.append(f"    {methods_id} --> {more_id}[\"... {len(methods) - 5} more methods\"]")
                        lines.append(f"    style {more_id} fill:#f5f5f5,stroke:#999")
                
                # Add class variables
                class_vars = cls.get('class_variables', [])
                if class_vars:
                    vars_id = f"{class_id}_VARS"
                    lines.append(f"    {class_id} --> {vars_id}[\"📊 Class Variables ({len(class_vars)})\"]")
                    lines.append(f"    style {vars_id} fill:#e0f2f1,stroke:#009688")
                    
                    for var in class_vars[:3]:
                        var_id = f"{class_id}_VAR_{var['name']}".replace(' ', '_')
                        lines.append(f"    {vars_id} --> {var_id}[\"{var['name']}\"]")
                        lines.append(f"    style {var_id} fill:#b2dfdb,stroke:#00796b")
        
        # Add top-level functions section
        if top_level_funcs:
            funcs_id = "FUNCTIONS"
            lines.append(f"    {root_id} --> {funcs_id}[\"⚙️ Top-Level Functions ({len(top_level_funcs)})\"]")
            lines.append(f"    style {funcs_id} fill:#fff4e6,stroke:#ff9800,stroke-width:2px")
            
            for func in top_level_funcs[:10]:  # Limit to 10 for readability
                func_id = f"FUNC_{func['name']}".replace(' ', '_')
                func_label = func['name']
                if func.get('is_async'):
                    func_label = f"🔁 {func_label}"
                func_label += "()"
                
                # Add parameter count
                params = func.get('parameters', [])
                if params:
                    param_count = len([p for p in params if p != 'self'])
                    if param_count > 0:
                        func_label += f"\\n({param_count} params)"
                
                lines.append(f"    {funcs_id} --> {func_id}[\"{func_label}\"]")
                lines.append(f"    style {func_id} fill:#e8f5e9,stroke:#4caf50")
            
            if len(top_level_funcs) > 10:
                more_funcs_id = "MORE_FUNCS"
                lines.append(f"    {funcs_id} --> {more_funcs_id}[\"... {len(top_level_funcs) - 10} more functions\"]")
                lines.append(f"    style {more_funcs_id} fill:#f5f5f5,stroke:#999")
        
        # Add nested functions section if any
        if nested_funcs:
            nested_id = "NESTED"
            lines.append(f"    {root_id} --> {nested_id}[\"🔗 Nested Functions ({len(nested_funcs)})\"]")
            lines.append(f"    style {nested_id} fill:#f3e5f5,stroke:#9c27b0")
            
            for func in nested_funcs[:5]:  # Limit to 5
                nested_func_id = f"NESTED_{func['name']}".replace(' ', '_')
                func_label = func['name']
                if func.get('is_async'):
                    func_label = f"🔁 {func_label}"
                func_label += "()"
                lines.append(f"    {nested_id} --> {nested_func_id}[\"{func_label}\"]")
                lines.append(f"    style {nested_func_id} fill:#fce4ec,stroke:#e91e63")
            
            if len(nested_funcs) > 5:
                more_nested_id = "MORE_NESTED"
                lines.append(f"    {nested_id} --> {more_nested_id}[\"... {len(nested_funcs) - 5} more nested\"]")
                lines.append(f"    style {more_nested_id} fill:#f5f5f5,stroke:#999")
        
        # Add global variables section
        global_vars = self.parse_result.get('global_variables', [])
        if global_vars:
            globals_id = "GLOBALS"
            lines.append(f"    {root_id} --> {globals_id}[\"🌍 Global Variables ({len(global_vars)})\"]")
            lines.append(f"    style {globals_id} fill:#e0f2f1,stroke:#009688")
            
            for var in global_vars[:5]:  # Limit to 5
                var_id = f"GLOBAL_{var.get('name', 'var')}".replace(' ', '_')
                var_name = var.get('name', 'variable')
                lines.append(f"    {globals_id} --> {var_id}[\"{var_name}\"]")
                lines.append(f"    style {var_id} fill:#b2dfdb,stroke:#00796b")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_combined_flowchart(self, funcs: List[Dict]) -> str:
        """Generate flowchart showing multiple functions."""
        lines = ["```mermaid", "flowchart TD"]
        
        # Create a node for each function
        for i, func in enumerate(funcs[:5]):  # Limit to 5 functions
            func_name = func['name']
            func_id = f"FUNC{i+1}"
            lines.append(f"    {func_id}([{func_name}])")
            
            # Show it has control flow
            func_flow = [cf for cf in self.control_flow if cf.get('function') == func_name]
            if func_flow:
                lines.append(f"    {func_id} --> FLOW{func_id}[Has {len(func_flow)} control structures]")
        
        lines.append("```")
        return "\n".join(lines)

