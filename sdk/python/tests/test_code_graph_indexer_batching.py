
import os
import pytest
import shutil
import tempfile
import json
from unittest.mock import MagicMock, patch
import sys

# Mock protobuf modules BEFORE importing CodeGraphIndexer
mock_pb2 = MagicMock()

def make_mock_request(query=None, namespace=None, triples=None):
    m = MagicMock()
    m.query = query
    m.triples = triples
    return m

mock_pb2.SparqlRequest.side_effect = make_mock_request
mock_pb2.IngestRequest.side_effect = make_mock_request
mock_pb2.Triple = MagicMock(return_value="mock_triple")

sys.modules['synapse.infrastructure.web.semantic_engine_pb2'] = mock_pb2
sys.modules['agents.proto.semantic_engine_pb2'] = mock_pb2
sys.modules['semantic_engine_pb2'] = mock_pb2

# Ensure sdk/python is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib import code_graph_indexer
# Patch the module-level variable directly to ensure it's not None
code_graph_indexer.semantic_engine_pb2 = mock_pb2
code_graph_indexer.semantic_engine_pb2_grpc = MagicMock()

from lib.code_graph_indexer import CodeGraphIndexer

class MockStub:
    def __init__(self):
        self.sparql_calls = []
        self.ingest_calls = []
        self.batch_results = [] # To configure return values

    def QuerySparql(self, request):
        self.sparql_calls.append(request.query)

        # If mocking batch results
        if "VALUES" in request.query and self.batch_results:
            return MagicMock(results_json=json.dumps(self.batch_results))

        # return empty results for other hashes
        return MagicMock(results_json="[]")

    def IngestTriples(self, request):
        self.ingest_calls.append(request)
        return MagicMock()

@pytest.fixture
def repo_dir():
    # Create temp dir with 10 files
    d = tempfile.mkdtemp()
    for i in range(10):
        with open(os.path.join(d, f"file_{i}.py"), "w") as f:
            f.write(f"def func_{i}(): pass")
    yield d
    shutil.rmtree(d)

@pytest.fixture
def indexer(repo_dir):
    indexer = CodeGraphIndexer(root_path=repo_dir)
    # Mock parser to avoid parsing overhead
    indexer.parser = MagicMock()
    # Return a dummy symbol so indexer attempts to process it
    indexer.parser.parse_file.return_value = {
        'filepath': 'dummy',
        'symbols': [{'name': 'func', 'type': 'function', 'start_line': 1, 'end_line': 1, 'hash': 'abc'}]
    }
    indexer.parser.languages = {'.py': 1} # Mock languages dict

    # Manually inject stub
    indexer.stub = MockStub()
    return indexer

def test_batch_query_optimization(indexer, repo_dir):
    """
    Verifies that the indexer batches SPARQL queries instead of calling per-file.
    Optimization works IF batch query returns data.
    """
    # Configure stub to return data for the files
    # We simulate that all files have symbols and hashes
    results = []
    for i in range(10):
        results.append({
            "file": {"value": f"http://swarm.os/file/file_{i}.py"},
            "symbol": {"value": f"http://swarm.os/symbol/file_{i}.py#func"},
            "hash": {"value": "abc"}
        })
    indexer.stub.batch_results = results

    indexer.index_repository()

    sparql_calls = indexer.stub.sparql_calls
    select_calls = [q for q in sparql_calls if "SELECT" in q]

    print(f"DEBUG: Optimization SELECT calls: {len(select_calls)}")
    # Should be 1 query (the batch one) because all files found in result.
    assert len(select_calls) == 1, f"Expected exactly 1 batch query, got {len(select_calls)}"


def test_batch_failure_fallback(indexer, repo_dir):
    """
    Verifies that if batch query returns empty (e.g., failure or missing data),
    indexer falls back to individual file queries to be robust.
    """
    # Configure stub to return NOTHING (empty list)
    indexer.stub.batch_results = []

    indexer.index_repository()

    sparql_calls = indexer.stub.sparql_calls
    select_calls = [q for q in sparql_calls if "SELECT" in q]

    print(f"DEBUG: Fallback SELECT calls: {len(select_calls)}")

    # 1 batch query + 10 individual queries = 11 calls
    # This proves fallback mechanism is active.
    assert len(select_calls) >= 11, f"Expected fallback to individual queries (>= 11 calls), got {len(select_calls)}"
