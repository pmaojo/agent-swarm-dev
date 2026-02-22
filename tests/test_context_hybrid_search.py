
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

class MockSearchMode:
    HYBRID = 2
    VECTOR_ONLY = 0
    GRAPH_ONLY = 1

class MockSearchResult:
    def __init__(self, content, score):
        self.content = content
        self.score = score

class MockSearchResponse:
    def __init__(self, results):
        self.results = results

class MockSemanticEnginePb2:
    SearchMode = MockSearchMode
    HybridSearchRequest = MagicMock()
    SearchResponse = MockSearchResponse
    SearchResult = MockSearchResult
    SparqlRequest = MagicMock()

# Patch the modules before importing ContextParser
sys.modules['agents.proto.semantic_engine_pb2'] = MockSemanticEnginePb2
sys.modules['semantic_engine_pb2'] = MockSemanticEnginePb2

sys.modules['agents.proto.semantic_engine_pb2_grpc'] = MagicMock()
sys.modules['semantic_engine_pb2_grpc'] = MagicMock()

# Now import ContextParser
from agents.tools.context import ContextParser

class TestHybridSearchFallback(unittest.TestCase):
    def setUp(self):
        pass

    @patch('agents.tools.context.read_file', return_value="def foo(): pass")
    def test_hybrid_search_fallback(self, mock_read_file):
        parser = ContextParser()
        parser.stub = MagicMock()

        # 1. Setup SPARQL to return empty results
        sparql_response = MagicMock()
        sparql_response.results_json = '[]'
        parser.stub.QuerySparql.return_value = sparql_response

        # 2. Setup HybridSearch to return results
        r1 = MockSearchResult("Related Lesson 1", 0.8)
        r2 = MockSearchResult("Related Lesson 2 (Low Score)", 0.4) # Should be filtered out (< 0.65)
        r3 = MockSearchResult("Related Lesson 3", 0.7)

        mock_search_resp = MockSearchResponse([r1, r2, r3])
        parser.stub.HybridSearch.return_value = mock_search_resp

        # 3. Execute
        filename = "test_file.py"
        context_text = "Fixing memory leak in python"
        input_text = f"Check @file:{filename} for issues. {context_text}"

        expanded_text = parser.expand_context(input_text)

        print("Expanded Text:\n", expanded_text)

        # Verify calls
        # SPARQL should be called
        parser.stub.QuerySparql.assert_called()

        # HybridSearch SHOULD be called now (but will fail until implemented)
        parser.stub.HybridSearch.assert_called()

        # Verify branding
        self.assertIn("### 🌌 Ecos de la Forja (Intuición de Synapse):", expanded_text)

        # Verify filtering and formatting
        self.assertIn("Related Lesson 1", expanded_text)
        self.assertIn("(Afinidad: 0.80)", expanded_text)
        self.assertIn("Related Lesson 3", expanded_text)
        self.assertIn("(Afinidad: 0.70)", expanded_text)

        self.assertNotIn("Related Lesson 2", expanded_text)

if __name__ == '__main__':
    unittest.main()
