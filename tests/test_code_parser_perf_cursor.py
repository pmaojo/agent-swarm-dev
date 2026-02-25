
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add sdk/python/lib to path
sys.path.append(os.path.join(os.getcwd(), "sdk/python/lib"))

from code_parser import CodeParser

class TestCodeParserPerformance(unittest.TestCase):

    def setUp(self):
        self.test_file = "temp_perf_test.py"
        # Create a dummy python file with many functions
        content = "class A:\n"
        for i in range(100):
            content += f"  def method_{i}(self):\n    print('hello')\n"

        with open(self.test_file, "w") as f:
            f.write(content)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_cursor_instantiation_optimization(self):
        parser = CodeParser()

        # We want to count how many times QueryCursor is instantiated
        with patch('code_parser.QueryCursor') as mock_cursor_cls:
            mock_instance = MagicMock()
            # We need the cursor to be returned by the constructor
            mock_cursor_cls.return_value = mock_instance

            # Mock node behavior
            mock_node = MagicMock()
            mock_node.start_byte = 0
            mock_node.end_byte = 10
            mock_node.start_point.row = 1
            mock_node.end_point.row = 2

            # Simulate 100 matches for the first call (definitions)
            matches_list = []
            for i in range(100):
                captures = {
                    'function': [mock_node],
                    'name': [mock_node],
                    'body': [mock_node]
                }
                # match format: (match_obj, captures_dict)
                matches_list.append((None, captures))

            # side_effect for matches():
            # 1. Definitions query -> returns 100 matches
            # 2. Calls query (for each function) -> returns empty list
            # 3. Inheritance query -> returns empty list
            # Note: If we reuse the cursor, matches() will be called on the SAME instance multiple times.
            # If we create new cursors, it will be called on new instances.
            # The side_effect list needs to cover all calls.
            # With optimization, matches() is called 1 + 100 + 1 = 102 times.
            # Without optimization, matches() is also called 102 times.
            # The optimization is about minimizing INSTANTIATION of QueryCursor.

            # So we just need to ensure matches() returns valid iterables.
            # We can use an infinite iterator or a long list.
            mock_instance.matches.side_effect = [matches_list] + [[]]*200

            parser.parse_file(self.test_file)

            print(f"QueryCursor instantiation count: {mock_cursor_cls.call_count}")

            # Assert that we are not creating a new cursor for every function
            # Ideally 1 (reused) or 3 (one per query type).
            # Definitely less than 50.
            self.assertLess(mock_cursor_cls.call_count, 10,
                f"QueryCursor was instantiated {mock_cursor_cls.call_count} times, expected < 10")

if __name__ == "__main__":
    unittest.main()
