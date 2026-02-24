
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

    def QuerySparql(self, request):
        self.sparql_calls.append(request.query)
        # return empty results for hashes
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
    Target: 1 query for 10 files (batch size >= 10).
    Current (FAIL): 10 queries.
    """
    indexer.index_repository()

    # We expect fewer calls than files if batched
    # Currently, it calls once per file to get hashes.
    # Plus maybe calls for deletion (if hash mismatch, but we return empty so no mismatch logic triggered usually,
    # except it thinks it's new symbol).

    # CodeGraphIndexer._get_existing_hashes is called once per file.
    # So we expect at least 10 calls.

    sparql_calls = indexer.stub.sparql_calls
    # Filter for SELECT queries (which fetch hashes)
    select_calls = [q for q in sparql_calls if "SELECT" in q]

    print(f"DEBUG: SELECT calls made: {len(select_calls)}")
    for i, call in enumerate(select_calls):
        print(f"Call {i}: {call}")

    # Assert optimization: We expect much fewer calls due to batching (e.g., 1 call for 10 files)
    assert len(select_calls) <= 2, f"Expected <= 2 SPARQL SELECT calls (optimized), got {len(select_calls)}"
