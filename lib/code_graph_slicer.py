import os
import sys
import json
import re
import logging
from typing import List, Dict, Set, Any, Tuple

# Ensure proto modules can import each other
proto_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'agents', 'proto'))
if proto_path not in sys.path and os.path.exists(proto_path):
    sys.path.append(proto_path)

# Imports
try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        try:
            import semantic_engine_pb2, semantic_engine_pb2_grpc
        except ImportError:
            semantic_engine_pb2 = None
            semantic_engine_pb2_grpc = None

from lib.code_parser import CodeParser

# Ontology Namespaces
SWARM = "http://swarm.os/ontology/"
CODEGRAPH = "http://swarm.os/ontology/codegraph/"
NIST = "http://nist.gov/caisi/"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CodeGraphSlicer")

class CodeGraphSlicer:
    def __init__(self):
        self.parser = CodeParser()
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None

    def connect(self):
        if not semantic_engine_pb2_grpc:
            logger.warning("Synapse gRPC modules not found. Slicing disabled.")
            return False

        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Synapse: {e}")
            return False

    def close(self):
        if self.channel:
            self.channel.close()

    def get_pruned_context(self, target_symbol_uri: str, max_depth: int = 2) -> Dict[str, Any]:
        """
        Retrieves the pruned context for a target symbol.
        Returns: {
            "context": str (The skeleton code),
            "original_size": int,
            "pruned_size": int,
            "savings_percent": float
        }
        """
        if not self.stub:
            if not self.connect():
                return {"context": "", "error": "No connection"}

        # 1. Find related nodes in the graph
        related_nodes = self._find_related_nodes(target_symbol_uri, max_depth)

        # 2. Group by file
        files_map = {} # file_uri -> list of nodes
        for node in related_nodes:
            file_uri = node['file']
            if file_uri not in files_map:
                files_map[file_uri] = []
            files_map[file_uri].append(node)

        # 3. Process each file to generate skeleton
        full_context = ""
        total_original_size = 0
        total_pruned_size = 0

        for file_uri, nodes in files_map.items():
            # file_uri is http://swarm.os/file/path/to/file.py
            # Extract relative path
            rel_path = file_uri.replace("http://swarm.os/file/", "")

            try:
                # Assuming local file access
                if not os.path.exists(rel_path):
                     logger.warning(f"File not found locally: {rel_path}")
                     continue

                with open(rel_path, 'r') as f:
                    content = f.read()

                original_size = len(content)
                total_original_size += original_size

                # Parse file to get structure
                parse_result = self.parser.parse_file(rel_path)
                symbols = parse_result.get('symbols', [])

                # Determine which ranges to keep full vs skeleton
                # Nodes in `nodes` list are "related".
                # If node URI == target_symbol_uri, keep FULL.
                # Else, keep SKELETON (signature + docstring).
                # Also check for Safety Nodes (# NIST-Hard-Constraint)

                skeleton_code = self._generate_skeleton(content, symbols, nodes, target_symbol_uri, rel_path)

                pruned_size = len(skeleton_code)
                total_pruned_size += pruned_size

                full_context += f"\nFile: {rel_path}\n```\n{skeleton_code}\n```\n"

            except Exception as e:
                logger.error(f"Error processing {rel_path}: {e}")

        savings = 0.0
        if total_original_size > 0:
            savings = (1.0 - (total_pruned_size / total_original_size)) * 100.0

        return {
            "context": full_context,
            "original_size": total_original_size,
            "pruned_size": total_pruned_size,
            "savings_percent": savings
        }

    def _find_related_nodes(self, target_uri: str, depth: int) -> List[Dict]:
        """
        Returns list of {uri, type, startLine, endLine, file}
        """
        # SPARQL Property Path to find reachable nodes
        # Also get their file and lines
        query = f"""
        PREFIX swarm: <{SWARM}>
        PREFIX codegraph: <{CODEGRAPH}>

        SELECT DISTINCT ?node ?file ?start ?end WHERE {{
            {{
                # The target itself
                BIND(<{target_uri}> AS ?node)
            }}
            UNION
            {{
                # Forward reachable
                <{target_uri}> (swarm:calls|swarm:references|swarm:inheritsFrom){{1,{depth}}} ?node .
            }}
            # Get metadata
            ?file swarm:hasSymbol ?node .
            ?node swarm:startLine ?start .
            ?node swarm:endLine ?end .
        }}
        """

        if not self.stub:
            return []

        try:
            request = semantic_engine_pb2.SparqlRequest(query=query, namespace="default")
            response = self.stub.QuerySparql(request)
            results = json.loads(response.results_json)

            nodes = []
            for r in results:
                nodes.append({
                    "uri": r['node']['value'],
                    "file": r['file']['value'],
                    "start": int(r['start']['value']),
                    "end": int(r['end']['value'])
                })
            return nodes
        except Exception as e:
            logger.error(f"SPARQL Error: {e}")
            return []

    def _generate_skeleton(self, content: str, all_symbols: List[Dict], related_nodes: List[Dict], target_uri: str, filepath: str) -> str:
        """
        Generates the skeleton code for a file.
        Uses a stack-based approach to handle nested symbols (Classes -> Methods).
        """
        lines = content.splitlines()

        # 1. Determine status of each symbol: FULL, SKELETON, PRUNE
        symbol_status = {} # index in all_symbols -> status

        # Map URI to status
        uri_status = {}
        target_found = False
        for node in related_nodes:
            if node['uri'] == target_uri:
                uri_status[node['uri']] = 'FULL'
                target_found = True
            else:
                uri_status[node['uri']] = 'SKELETON'

        # Match all_symbols to URIs (heuristic by name/line)
        # We need to know which symbol corresponds to which URI.
        # Since we don't have URIs in all_symbols here (CodeParser output), we must reconstruct or use lines.
        # But we have `related_nodes` which has start/end lines.

        # Assign status based on overlap with related_nodes
        for idx, sym in enumerate(all_symbols):
            status = 'PRUNE' # Default

            # Check overlap with related nodes
            # A symbol might cover a related node (container)
            # Or be covered by a related node (member)

            # Case 1: Exact Match (It IS the related node)
            for node in related_nodes:
                if node['start'] == sym['start_line'] and node['end'] == sym['end_line']:
                    status = uri_status.get(node['uri'], 'SKELETON')
                    break

            # Case 2: Containment (If parent is FULL, child is FULL)
            # Actually, bubble down is safer for FULL.
            # But here we bubble up SKELETON in step 1b.

            # If no direct match, check if it contains a related node?
            # Step 1b handles "If child is interesting, parent must be SKELETON".

            # What if parent is related (SKELETON)? Should children be SKELETON or PRUNE?
            # If Class A is SKELETON, its methods should be SKELETON (signatures visible).
            # But currently default is PRUNE.
            # So we need "Bubble Down" logic too?
            # If Parent is SKELETON -> Children are SKELETON (signatures)
            # If Parent is FULL -> Children are FULL.

            symbol_status[idx] = status

            # Check Safety (NIST)
            # Scan lines of symbol
            for l in range(sym['start_line'], sym['end_line'] + 1):
                if l <= len(lines) and "# NIST-Hard-Constraint" in lines[l-1]:
                    status = 'FULL'
                    break

            symbol_status[idx] = status

        # 1b. Propagate status (Bubble Up and Bubble Down)

        # Bubble Up: If child is interesting, parent must be SKELETON (to show container)
        changed = True
        while changed:
            changed = False
            for idx, sym in enumerate(all_symbols):
                if symbol_status[idx] == 'PRUNE':
                    for child_idx, child in enumerate(all_symbols):
                        if idx == child_idx: continue
                        if child['start_line'] >= sym['start_line'] and child['end_line'] <= sym['end_line']:
                            if symbol_status[child_idx] != 'PRUNE':
                                symbol_status[idx] = 'SKELETON'
                                changed = True
                                break

        # Bubble Down: If parent is SKELETON, children should be SKELETON (signatures)
        # Unless explicitly PRUNE? No, usually we want to see members of a related class.
        # But we only want to see *signatures*.
        # Wait, if `method` was not in `related_nodes`, it is PRUNE.
        # But if `Class A` is related (SKELETON), we expect to see `def method(...)` inside.
        # So we MUST bubble down SKELETON status to children.

        # Sort by size (largest first) to propagate down
        # Actually just iterate: for each symbol, if SKELETON/FULL, set children.

        # We need to be careful not to overwrite FULL with SKELETON.

        for idx, sym in enumerate(all_symbols):
            parent_status = symbol_status[idx]
            if parent_status in ['SKELETON', 'FULL']:
                target_child_status = 'SKELETON' if parent_status == 'SKELETON' else 'FULL'

                for child_idx, child in enumerate(all_symbols):
                    if idx == child_idx: continue
                    if child['start_line'] >= sym['start_line'] and child['end_line'] <= sym['end_line']:
                        current_child = symbol_status[child_idx]
                        if current_child == 'PRUNE':
                             symbol_status[child_idx] = target_child_status
                        # Don't downgrade FULL to SKELETON

        # 2. Iterate lines with stack
        generated = []
        i = 1

        # Sort symbols by start line
        # Store as (start_line, end_line, type, index)
        # We need access to original index for status lookup
        sorted_symbols = []
        for idx, sym in enumerate(all_symbols):
            sorted_symbols.append({
                'start': sym['start_line'],
                'end': sym['end_line'],
                'type': sym['type'],
                'idx': idx
            })
        sorted_symbols.sort(key=lambda x: x['start'])

        stack = [] # List of {'end': int, 'status': str, 'type': str}

        while i <= len(lines):
            line_content = lines[i-1]

            # Check for started symbols
            # There might be multiple starting on same line (unlikely but possible)
            # We want the outermost first? No, if we iterate lines, we encounter start.
            # If multiple start at same line, the one with larger end is outer?
            starting_syms = [s for s in sorted_symbols if s['start'] == i]
            # Sort by end descending (outer first)
            starting_syms.sort(key=lambda x: x['end'], reverse=True)

            for sym in starting_syms:
                status = symbol_status[sym['idx']]
                stack.append({
                    'start': sym['start'],
                    'end': sym['end'],
                    'status': status,
                    'type': sym['type']
                })

            # Determine action based on Top of Stack
            action = 'KEEP'
            if stack:
                top = stack[-1]
                action = top['status']

                # Handling SKELETON logic
                if action == 'SKELETON':
                    # If it's a Class, we want to print signature and recurse (KEEP)
                    if top['type'] in ['class', 'impl']:
                        action = 'KEEP' # Treat contents as visible unless inner symbols override
                    else:
                        # Function/Method -> Print Signature + ... then SKIP
                        pass

            # Execute Action
            if action == 'FULL' or action == 'KEEP':
                generated.append(line_content)
                i += 1
            elif action == 'SKELETON':
                # Leaf skeleton (Function/Method)

                # Check for one-liners
                if stack and stack[-1]['start'] == stack[-1]['end']:
                    generated.append(line_content)
                    i += 1
                    while stack and stack[-1]['end'] < i: stack.pop()
                    continue

                generated.append(line_content)
                stripped = line_content.strip()

                # Heuristic to detect start of body
                if stripped.endswith(':') or stripped.endswith('{') or stripped.endswith(';'):

                    # 1. Handle Docstrings (Python)
                    # Look ahead for docstring
                    j = i + 1
                    if filepath.endswith('.py'):
                        if j <= len(lines):
                            next_line = lines[j-1].strip()
                            if next_line.startswith('"""') or next_line.startswith("'''"):
                                quote = next_line[:3]
                                generated.append(lines[j-1])
                                j += 1
                                if not next_line.endswith(quote) or len(next_line) == 3:
                                    while j <= len(lines):
                                        l = lines[j-1]
                                        generated.append(l)
                                        j += 1
                                        if l.strip().endswith(quote):
                                            break

                    # 2. Insert Ellipsis
                    indent = len(line_content) - len(line_content.lstrip())
                    indent_str = " " * (indent + 4)
                    comment_char = "#" if filepath.endswith('.py') else "//"
                    ellipsis = "..." if filepath.endswith('.py') or filepath.endswith('.js') else "/* ... */"
                    generated.append(f"{indent_str}{ellipsis} {comment_char} Pruned")

                    # 3. Handle Closing Brace (Non-Python)
                    if not filepath.endswith('.py'):
                        generated.append(" " * indent + "}")

                    # Skip to end of this symbol
                    skip_to = stack[-1]['end']
                    i = skip_to + 1
                else:
                    # Still in signature?
                    i += 1

            elif action == 'PRUNE':
                i += 1

            # Check for ended symbols
            # We need to pop any symbol that ends at `i - 1` (the line we just processed/skipped)
            # But wait, if we skipped to `skip_to + 1`, we effectively processed up to `skip_to`.
            # So any symbol ending <= `i-1` should be popped.

            # Clean stack
            # Remove symbols that have ended.
            # Since symbols nest, the top should end first (or same time).
            while stack and stack[-1]['end'] < i:
                stack.pop()

        return "\n".join(generated)

if __name__ == "__main__":
    # Test
    slicer = CodeGraphSlicer()
    # Mocking would be needed for real test without Synapse
