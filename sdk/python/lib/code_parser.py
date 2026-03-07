"""
Code Parser using Tree-sitter.
Extracts symbols, calls, and relationships for the CodeGraph.
"""
import os
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Set

import tree_sitter_python
import tree_sitter_rust
import tree_sitter_javascript
import tree_sitter_cpp
from tree_sitter import Language, Parser, Query

class CodeParser:
    """
    Code Parser using Tree-sitter.
    Extracts symbols, calls, and relationships for the CodeGraph.

    @synapse:rule Dynamically handle tree-sitter capture extraction and cache execution strategy in `execution_strategies` per query type to avoid try-except overhead in hot loops.
    @synapse:rule Instantiate `QueryCursor` locally per `parse_file` execution to ensure thread-safety and keep O(1) instantiation overhead for repetitive queries.
    """
    def __init__(self):
        self.languages = {
            ".py": Language(tree_sitter_python.language()),
            ".rs": Language(tree_sitter_rust.language()),
            ".js": Language(tree_sitter_javascript.language()),
            ".ts": Language(tree_sitter_javascript.language()), # JS parser often works for TS basics
            ".cpp": Language(tree_sitter_cpp.language()),
            ".c": Language(tree_sitter_cpp.language()), # C++ parser often handles C
            ".h": Language(tree_sitter_cpp.language()),
            ".hpp": Language(tree_sitter_cpp.language()),
        }
        self.parsers = {}
        for ext, lang in self.languages.items():
            self.parsers[ext] = Parser(lang)

        # Cache for compiled queries: (ext, query_type) -> Query
        self.query_cache: Dict[Tuple[str, str], Optional[Query]] = {}

        # Cache for execution strategy: (ext, query_type) -> strategy function
        self.execution_strategies: Dict[Tuple[str, str], Any] = {}

    def _get_compiled_query(self, lang: Language, lang_ext: str, query_type: str) -> Optional[Query]:
        """
        Returns a compiled Query object, using cache if available.
        @synapse:rule Cache compiled Tree-sitter queries to avoid redundant compilation overhead (performance optimization).
        """
        cache_key = (lang_ext, query_type)
        if cache_key in self.query_cache:
            return self.query_cache[cache_key]

        query_str = self._get_query(lang_ext, query_type)
        if not query_str:
            self.query_cache[cache_key] = None
            return None

        try:
            query = Query(lang, query_str)
            self.query_cache[cache_key] = query
            return query
        except Exception as e:
            print(f"Error compiling query for {lang_ext} {query_type}: {e}")
            self.query_cache[cache_key] = None
            return None

    def _get_query_obj(self, lang: Language, lang_ext: str, query_type: str) -> Optional[Query]:
        """
        Returns a compiled Query object, using cache if available.
        """
        return self._get_compiled_query(lang, lang_ext, query_type)

    def _get_query(self, lang_ext: str, query_type: str) -> Optional[str]:
        # Define queries for each language
        # Python
        if lang_ext == ".py":
            if query_type == "definitions":
                return """
                (class_definition
                    name: (identifier) @name
                    body: (block) @body) @class
                (function_definition
                    name: (identifier) @name
                    body: (block) @body) @function
                """
            elif query_type == "calls":
                return """
                (call function: (identifier) @func_name)
                (call function: (attribute attribute: (identifier) @func_name))
                """
            elif query_type == "imports":
                return """
                (import_statement) @import
                (import_from_statement) @import
                """
            elif query_type == "inheritance":
                return """
                (class_definition
                    name: (identifier) @classname
                    superclasses: (argument_list (identifier) @superclass))
                """

        # Rust
        elif lang_ext == ".rs":
            if query_type == "definitions":
                return """
                (struct_item name: (type_identifier) @name) @class
                (impl_item type: (type_identifier) @name) @impl
                (function_item name: (identifier) @name body: (block) @body) @function
                """
            elif query_type == "calls":
                return """
                (call_expression function: (identifier) @func_name)
                (call_expression function: (field_expression field: (field_identifier) @func_name))
                """
            elif query_type == "imports":
                return """
                (use_declaration) @import
                """

        # JavaScript / TypeScript
        elif lang_ext in [".js", ".ts"]:
            if query_type == "definitions":
                return """
                (class_declaration name: (identifier) @name body: (class_body) @body) @class
                (function_declaration name: (identifier) @name body: (statement_block) @body) @function
                (method_definition name: (property_identifier) @name body: (statement_block) @body) @method
                """
            elif query_type == "calls":
                return """
                (call_expression function: (identifier) @func_name)
                (call_expression function: (member_expression property: (property_identifier) @func_name))
                """
            elif query_type == "imports":
                return """
                (import_statement) @import
                """
            elif query_type == "inheritance":
                return """
                (class_declaration
                    name: (identifier) @classname
                    class_heritage: (class_heritage (identifier) @superclass))
                """

        # C++
        elif lang_ext in [".cpp", ".h", ".hpp", ".c"]:
            if query_type == "definitions":
                return """
                (class_specifier name: (type_identifier) @name body: (field_declaration_list) @body) @class
                (function_definition declarator: (function_declarator declarator: (identifier) @name) body: (compound_statement) @body) @function
                """
            elif query_type == "calls":
                return """
                (call_expression function: (identifier) @func_name)
                (call_expression function: (field_expression field: (field_identifier) @func_name))
                """
            elif query_type == "imports":
                return """
                (preproc_include) @import
                """
            elif query_type == "inheritance":
                return """
                (class_specifier
                    name: (type_identifier) @classname
                    base_class_clause: (base_class_clause (type_identifier) @superclass))
                """

        return None

    def _execute_query(self, query: Query, node: Any, lang_ext: str, query_type: str, cursor: Optional[Any] = None) -> List[Any]:
        """
        Executes a query against a node, using a dynamically determined and cached execution strategy.
        This handles compatibility across different `tree-sitter` API versions (e.g., <0.22 vs >=0.22).

        @synapse:rule Cache execution strategies to avoid try-except overhead in hot loops.
        """
        cache_key = (lang_ext, query_type)
        if cache_key in self.execution_strategies:
            strategy = self.execution_strategies[cache_key]
            return strategy(query, node, cursor)

        # Determine strategy
        def strategy_query_matches(q, n, c):
            return q.matches(n)

        def strategy_cursor_matches_with_query(q, n, c):
            return c.matches(q, n)

        def strategy_cursor_matches(q, n, c):
            return c.matches(n)

        strategy = None

        if hasattr(query, 'matches'):
            try:
                # Test query.matches
                query.matches(node)
                strategy = strategy_query_matches
            except Exception:
                pass

        if strategy is None and cursor is not None:
            if hasattr(cursor, 'matches'):
                try:
                    # Test cursor.matches(node) (tree-sitter >= 0.22 where QueryCursor takes query in __init__)
                    cursor.matches(node)
                    strategy = strategy_cursor_matches
                except Exception:
                    try:
                        # Test cursor.matches(query, node) (some intermediate versions)
                        cursor.matches(query, node)
                        strategy = strategy_cursor_matches_with_query
                    except Exception:
                        pass

        if strategy is None:
            # Fallback to empty list if no strategy works
            strategy = lambda q, n, c: []

        self.execution_strategies[cache_key] = strategy
        return strategy(query, node, cursor)

    class CaptureMatch:
        """Helper to unify capture representations between old and new tree-sitter APIs."""
        def __init__(self, captures_dict_or_list):
            self.captures = {}
            if isinstance(captures_dict_or_list, dict):
                self.captures = captures_dict_or_list
            elif isinstance(captures_dict_or_list, list):
                # old format: list of tuples (node, capture_name)
                for node, name in captures_dict_or_list:
                    if name not in self.captures:
                        self.captures[name] = []
                    self.captures[name].append(node)

    def _normalize_matches(self, matches: List[Any]) -> List[CaptureMatch]:
        """Normalizes the return value of matches to a common structure."""
        normalized = []
        for match in matches:
            if isinstance(match, tuple) and len(match) == 2:
                # Newer versions return (pattern_index, captures_dict)
                normalized.append(self.CaptureMatch(match[1]))
            elif hasattr(match, 'captures'):
                # Older versions return objects with a `captures` attribute (list of tuples)
                normalized.append(self.CaptureMatch(match.captures))
            else:
                # Direct captures format
                normalized.append(self.CaptureMatch(match))
        return normalized

    def parse_file(self, filepath: str) -> Dict[str, Any]:
        """Parses a file and returns extracted symbols and relationships."""
        ext = os.path.splitext(filepath)[1]
        if ext not in self.languages:
            return {}

        try:
            with open(filepath, 'rb') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return {}

        lang = self.languages[ext]
        parser = self.parsers[ext]
        tree = parser.parse(content)
        root = tree.root_node

        symbols = []

        # Local cache for QueryCursor instances to ensure O(1) instantiation and thread-safety
        import tree_sitter
        cursors: Dict[str, Any] = {}

        def get_cursor(query_type: str, q: Query):
            if query_type not in cursors:
                try:
                    # tree-sitter >= 0.22 requires query as arg
                    cursors[query_type] = tree_sitter.QueryCursor(q)
                except Exception:
                    try:
                        cursors[query_type] = tree_sitter.QueryCursor()
                    except Exception:
                        cursors[query_type] = None
            return cursors[query_type]

        # 1. Extract Definitions (Classes, Functions)
        query = self._get_query_obj(lang, ext, "definitions")
        if query:
            try:
                cursor = get_cursor("definitions", query)
                raw_matches = self._execute_query(query, root, ext, "definitions", cursor)
                matches = self._normalize_matches(raw_matches)

                for match in matches:
                    captures = match.captures

                    node_type = "unknown"
                    name_node = None
                    body_node = None
                    def_node = None

                    # Check what we captured
                    if 'class' in captures:
                        node_type = "class"
                        def_node = captures['class'][0]
                    elif 'function' in captures:
                        node_type = "function"
                        def_node = captures['function'][0]
                    elif 'impl' in captures:
                        node_type = "impl"
                        def_node = captures['impl'][0]
                    elif 'method' in captures:
                        node_type = "function" # treat method as function
                        def_node = captures['method'][0]

                    if not def_node:
                        continue

                    if 'name' in captures:
                        name_node = captures['name'][0]
                    if 'body' in captures:
                        body_node = captures['body'][0]

                    if name_node:
                        name = content[name_node.start_byte:name_node.end_byte].decode('utf-8')
                        start_line = def_node.start_point.row + 1
                        end_line = def_node.end_point.row + 1

                        # Calculate hash of the body (or full node if body missing)
                        hash_content = content[def_node.start_byte:def_node.end_byte]
                        node_hash = hashlib.sha256(hash_content).hexdigest()

                        # Analyze body for calls
                        calls = set()
                        if body_node:
                            calls_query = self._get_query_obj(lang, ext, "calls")
                            calls_cursor = None
                            if calls_query:
                                calls_cursor = get_cursor("calls", calls_query)
                            calls = self._extract_calls(body_node, lang, ext, content, calls_query, calls_cursor)

                        symbols.append({
                            "name": name,
                            "type": node_type,
                            "start_line": start_line,
                            "end_line": end_line,
                            "hash": node_hash,
                            "calls": list(calls),
                            #"node": def_node # Keep node ref for further processing if needed
                        })
            except Exception as e:
                print(f"Error parsing definitions in {filepath}: {e}")

        # 2. Extract Inheritance
        inherit_query = self._get_query_obj(lang, ext, "inheritance")
        inherit_cursor = None
        if inherit_query:
            inherit_cursor = get_cursor("inheritance", inherit_query)
        inheritance_map = self._extract_inheritance(root, lang, ext, content, inherit_query, inherit_cursor)
        # Merge into symbols
        for sym in symbols:
            if sym['name'] in inheritance_map:
                sym['inherits_from'] = inheritance_map[sym['name']]

        return {
            "filepath": filepath,
            "language": ext,
            "symbols": symbols
        }

    def _extract_calls(self, node, lang, ext, content, query=None, cursor=None) -> Set[str]:
        calls = set()
        if not query:
            query = self._get_query_obj(lang, ext, "calls")
        if not query:
            return calls

        try:
            raw_matches = self._execute_query(query, node, ext, "calls", cursor)
            matches = self._normalize_matches(raw_matches)
            for match in matches:
                captures = match.captures
                if 'func_name' in captures:
                    for n in captures['func_name']:
                        func_name = content[n.start_byte:n.end_byte].decode('utf-8')
                        calls.add(func_name)
        except Exception as e:
            # print(f"Error extracting calls: {e}")
            pass
        return calls

    def _extract_inheritance(self, node, lang, ext, content, query=None, cursor=None) -> Dict[str, List[str]]:
        # Map class_name -> list of superclasses
        inheritance = {}
        if not query:
            query = self._get_query_obj(lang, ext, "inheritance")
        if not query:
            return inheritance

        try:
            raw_matches = self._execute_query(query, node, ext, "inheritance", cursor)
            matches = self._normalize_matches(raw_matches)

            for match in matches:
                captures = match.captures
                if 'classname' in captures and 'superclass' in captures:
                    class_name_node = captures['classname'][0]
                    class_name = content[class_name_node.start_byte:class_name_node.end_byte].decode('utf-8')

                    if class_name not in inheritance:
                        inheritance[class_name] = []

                    for sc in captures['superclass']:
                        superclass = content[sc.start_byte:sc.end_byte].decode('utf-8')
                        inheritance[class_name].append(superclass)
        except Exception as e:
             # print(f"Error extracting inheritance: {e}")
             pass

        return inheritance

if __name__ == "__main__":
    # Test
    parser = CodeParser()
    # Create a dummy file to test
    with open("test_parser.py", "w") as f:
        f.write("class A:\n  def method(self):\n    print('hello')\n\nclass B(A):\n  pass\n\ndef func():\n  return A()")

    result = parser.parse_file("test_parser.py")
    import json
    # Remove node objects for printing
    for s in result.get('symbols', []):
        if 'node' in s: del s['node']
    print(json.dumps(result, indent=2))
    os.remove("test_parser.py")
