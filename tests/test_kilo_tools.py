import unittest
import os
import sys
from unittest.mock import MagicMock, patch

# Add path to root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.tools.context import ContextParser
from agents.tools.knowledge import KnowledgeHarvester
from agents.tools.browser import BrowserTool

class TestKiloTools(unittest.TestCase):
    def setUp(self):
        # Mock Synapse
        self.mock_stub = MagicMock()

    def test_context_parser_expand(self):
        parser = ContextParser()
        parser.stub = self.mock_stub

        # Create a dummy file
        with open("dummy.txt", "w") as f:
            f.write("Hello World")

        text = "Check @file:dummy.txt please."
        expanded = parser.expand_context(text)

        self.assertIn("Hello World", expanded)
        self.assertIn("--- Context ---", expanded)

        os.remove("dummy.txt")

    def test_knowledge_harvester_scan(self):
        harvester = KnowledgeHarvester()
        # Mocking ingestion
        harvester.stub = self.mock_stub

        with open("dummy_code.py", "w") as f:
            f.write("# @synapse:constraint Use snake_case.\n# @synapse:lesson Avoid hardcoding.")

        triples = harvester.scan_file("dummy_code.py")

        self.assertEqual(len(triples), 3) # 1 file prop + 1 constraint + 1 lesson
        self.assertEqual(triples[1]['object'], '"Use snake_case."')

        os.remove("dummy_code.py")

    @patch('agents.tools.browser.requests.post')
    def test_browser_search(self, mock_post):
        # Mock requests response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """
        <div class="result">
            <h2 class="result__title">
                <a class="result__a" href="http://example.com">Example Title</a>
            </h2>
            <a class="result__snippet">Example Snippet</a>
        </div>
        """
        mock_post.return_value = mock_resp

        browser = BrowserTool()
        results = browser.search_documentation("test query")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "Example Title")
        self.assertEqual(results[0]['url'], "http://example.com")

if __name__ == '__main__':
    unittest.main()
