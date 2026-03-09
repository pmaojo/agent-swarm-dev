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
from tree_sitter import Language, Parser, Query, QueryCursor

class CodeParser:
    """
    Code Parser using Tree-sitter.
    Extracts symbols, calls, and relationships for the CodeGraph.
    @synapse:rule Cache QueryCursor locally per `parse_file` execution to ensure thread-safety and constant O(1) instantiation overhead for repetitive queries.
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

        # Cache for execution strategies across tree-sitter versions
        self.execution_strategies: Dict[str, str] = {}

    def _execute_query(self, lang: Language, ext: str, query_type: str, node: Any, local_cursors: Dict[str, QueryCursor]) -> List[Any]:
        query = self._get_query_obj(lang, ext, query_type)
        if not query:
            return []

        # Get or create local QueryCursor
        if query_type not in local_cursors:
            try:
                # >= 0.25 (and some 0.22+) takes Query in constructor
                local_cursors[query_type] = QueryCursor(query)
            except TypeError:
                # Older might not take args
                local_cursors[query_type] = QueryCursor()

        cursor = local_cursors[query_type]

        strategy = self.execution_strategies.get(query_type)

        if strategy == "cursor_matches_node":
            matches = cursor.matches(node)
            if matches and isinstance(matches[0], tuple):
                return [type('Match', (), {'captures': m[1]})() for m in matches]
            return matches
        elif strategy == "cursor_matches_query_node":
            matches = cursor.matches(query, node)
            if matches and isinstance(matches[0], tuple):
                return [type('Match', (), {'captures': m[1]})() for m in matches]
            return matches
        elif strategy == "query_matches_node":
            return query.matches(node)

        # Determine strategy if not cached
        try:
            # Fallback to older API first (if Query has matches)
            matches = query.matches(node)
            self.execution_strategies[query_type] = "query_matches_node"
            return matches
        except AttributeError:
            try:
                # Try tree-sitter 0.25+ / >= 0.22 API (cursor initialized with query)
                matches = cursor.matches(node)
                # In 0.25.2, cursor.matches returns a list of tuples like (match_id, {capture_name: [nodes]})
                # but the previous code expected objects with a .captures attribute.
                # If it's the new tuple format, let's wrap it.
                self.execution_strategies[query_type] = "cursor_matches_node"
                if matches and isinstance(matches[0], tuple):
                    return [type('Match', (), {'captures': m[1]})() for m in matches]
                return matches
            except TypeError:
                try:
                    # Try middle API
                    matches = cursor.matches(query, node)
                    self.execution_strategies[query_type] = "cursor_matches_query_node"
                    if matches and isinstance(matches[0], tuple):
                        return [type('Match', (), {'captures': m[1]})() for m in matches]
                    return matches
                except Exception:
                    pass
        except Exception:
            pass

        return []

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

        local_cursors: Dict[str, QueryCursor] = {}

        # 1. Extract Definitions (Classes, Functions)
        try:
            matches = self._execute_query(lang, ext, "definitions", root, local_cursors)

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
                            calls = self._extract_calls(body_node, lang, ext, content, local_cursors)

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
        inheritance_map = self._extract_inheritance(root, lang, ext, content, local_cursors)
        # Merge into symbols
        for sym in symbols:
            if sym['name'] in inheritance_map:
                sym['inherits_from'] = inheritance_map[sym['name']]

        return {
            "filepath": filepath,
            "language": ext,
            "symbols": symbols
        }

    def _extract_calls(self, node, lang, ext, content, local_cursors: Dict[str, QueryCursor]) -> Set[str]:
        calls = set()

        try:
            matches = self._execute_query(lang, ext, "calls", node, local_cursors)
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

    def _extract_inheritance(self, node, lang, ext, content, local_cursors: Dict[str, QueryCursor]) -> Dict[str, List[str]]:
        # Map class_name -> list of superclasses
        inheritance = {}

        try:
            matches = self._execute_query(lang, ext, "inheritance", node, local_cursors)

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
