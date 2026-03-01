
import pytest
from unittest.mock import MagicMock, patch
from sdk.python.lib.code_parser import CodeParser
try:
    from tree_sitter import QueryCursor, Node
except ImportError:
    from tree_sitter import Node
    class QueryCursor:
        pass

def test_query_cursor_instantiations():
    """
    Verifies that QueryCursor is instantiated a minimal number of times (O(1))
    regardless of the number of functions/definitions in the file.
    """

    # Generate a Python file with 10 functions
    content = ""
    for i in range(10):
        content += f"def func_{i}():\n    print('hello')\n    other_func()\n\n"

    try:
        from tree_sitter import QueryCursor
        target_patch = 'tree_sitter.QueryCursor'
    except ImportError:
        target_patch = 'sdk.python.lib.code_parser.QueryCursor'

    # Only patch if QueryCursor actually exists where we expect it
    with patch(target_patch, create=True) as MockCursor:
        # MockCursor is called 3 times now:
        # 1. definitions
        # 2. inheritance
        # 3. calls (reused!)

        # We need to configure the return values so they work with the reused instances.

        mock_node_func = MagicMock(spec=Node)
        mock_node_func.start_point.row = 0
        mock_node_func.end_point.row = 1
        mock_node_func.start_byte = 0
        mock_node_func.end_byte = 10
        mock_node_name = MagicMock(spec=Node)
        mock_node_name.start_byte = 4
        mock_node_name.end_byte = 8
        mock_node_body = MagicMock(spec=Node)

        captures_def = {
            'function': [mock_node_func],
            'name': [mock_node_name],
            'body': [mock_node_body]
        }

        # Create persistent mock instances for each type
        cursor_def = MagicMock()
        cursor_def.matches.return_value = [(0, captures_def)] * 10

        cursor_calls = MagicMock()
        cursor_calls.matches.return_value = [] # No calls found, to simplify

        cursor_inheritance = MagicMock()
        cursor_inheritance.matches.return_value = []

        # side_effect needs to match the order of FIRST instantiation
        # 1. definitions
        # 2. inheritance
        # 3. calls (inside loop)

        # Wait, the order in code is:
        # 1. definitions
        # 2. inheritance (at end of parse_file)
        # BUT inside definitions loop, we call _extract_calls.
        # So:
        # 1. definitions (instantiate) -> returns matches
        #    Loop match 1:
        #      _extract_calls -> calls (instantiate)
        #    Loop match 2:
        #      _extract_calls -> calls (CACHED)
        # ...
        # End loop
        # 2. inheritance (instantiate)

        # So total instantiations should be 3.

        MockCursor.side_effect = [cursor_def, cursor_calls, cursor_inheritance]

        parser = CodeParser()

        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            parser.parse_file(tmp_path)

            call_count = MockCursor.call_count
            print(f"QueryCursor instantiated {call_count} times.")

            # Now we expect <= 5 (O(1))
            assert call_count <= 5, f"Expected <= 5 instantiations (O(1)), got {call_count}"

        finally:
            os.remove(tmp_path)
