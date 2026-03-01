import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch

# Mock gRPC modules before any imports
semantic_engine_pb2_mock = MagicMock()
semantic_engine_pb2_grpc_mock = MagicMock()
codegraph_pb2_mock = MagicMock()

sys.modules['semantic_engine_pb2'] = semantic_engine_pb2_mock
sys.modules['semantic_engine_pb2_grpc'] = semantic_engine_pb2_grpc_mock
sys.modules['agents.synapse_proto.codegraph_pb2'] = codegraph_pb2_mock

# Add necessary stubs to pb2 mocks
class FakeSparqlRequest:
    def __init__(self, query="", namespace="default"):
        self.query = query
        self.namespace = namespace

semantic_engine_pb2_mock.SparqlRequest = FakeSparqlRequest
semantic_engine_pb2_mock.IngestRequest = MagicMock()
semantic_engine_pb2_mock.Triple = MagicMock()

from lib.code_graph_indexer import CodeGraphIndexer

@pytest.fixture
def mock_indexer():
    with patch('lib.code_graph_indexer.CodeParser') as MockParser:
        indexer = CodeGraphIndexer(root_path=".")
        indexer.stub = MagicMock()

        # Mock parser to return some dummy symbols
        mock_parser_instance = MockParser.return_value
        mock_parser_instance.languages = {'.py'}

        # Define mock file processing
        def mock_parse_file(filepath):
            if filepath.endswith('file1.py'):
                return {'symbols': [{'type': 'function', 'name': 'func1', 'qualified_name': 'func1', 'hash': 'hash1', 'start_line': 1, 'end_line': 10}]}
            elif filepath.endswith('file2.py'):
                return {'symbols': [{'type': 'class', 'name': 'Class1', 'qualified_name': 'Class1', 'hash': 'hash2', 'start_line': 1, 'end_line': 20}]}
            return None

        mock_parser_instance.parse_file.side_effect = mock_parse_file
        indexer.parser = mock_parser_instance
        yield indexer

def test_batch_optimization_success(mock_indexer):
    file_uris = ['http://swarm.os/file/file1.py', 'http://swarm.os/file/file2.py']

    # Mock successful batch SPARQL response
    mock_response = MagicMock()
    mock_response.results_json = json.dumps([
        {
            "file": {"value": "http://swarm.os/file/file1.py"},
            "symbol": {"value": "http://swarm.os/symbol/file1.py#func1"},
            "hash": {"value": "hash1"}
        },
        {
            "file": {"value": "http://swarm.os/file/file2.py"},
            "symbol": {"value": "http://swarm.os/symbol/file2.py#Class1"},
            "hash": {"value": "old_hash"}
        }
    ])
    mock_indexer.stub.QuerySparql.return_value = mock_response

    batch_hashes = mock_indexer._get_batch_existing_hashes(file_uris)

    assert batch_hashes is not None
    assert 'http://swarm.os/file/file1.py' in batch_hashes
    assert 'http://swarm.os/file/file2.py' in batch_hashes
    assert batch_hashes['http://swarm.os/file/file1.py']['http://swarm.os/symbol/file1.py#func1'] == 'hash1'
    assert batch_hashes['http://swarm.os/file/file2.py']['http://swarm.os/symbol/file2.py#Class1'] == 'old_hash'

    # Ensure QuerySparql was called once for the batch
    assert mock_indexer.stub.QuerySparql.call_count == 1

    # Ensure QuerySparql was called once for the batch
    call_args = mock_indexer.stub.QuerySparql.call_args[0][0]
    # Check that VALUES clause was generated
    assert "VALUES ?file { <http://swarm.os/file/file1.py> <http://swarm.os/file/file2.py> }" in call_args.query

def test_batch_optimization_fallback(mock_indexer):
    file_uris = ['http://swarm.os/file/file1.py', 'http://swarm.os/file/file2.py']

    # Mock batch SPARQL exception to simulate failure
    mock_indexer.stub.QuerySparql.side_effect = Exception("gRPC Error")

    batch_hashes = mock_indexer._get_batch_existing_hashes(file_uris)

    # Batch should fail and return None
    assert batch_hashes is None

    # Reset side effect for subsequent per-file lookups
    mock_indexer.stub.QuerySparql.side_effect = None

    # Mock per-file responses
    def mock_query_sparql_per_file(request):
        mock_resp = MagicMock()
        if 'file1.py' in request.query:
            mock_resp.results_json = json.dumps([{"symbol": {"value": "http://swarm.os/symbol/file1.py#func1"}, "hash": {"value": "hash1"}}])
        elif 'file2.py' in request.query:
            mock_resp.results_json = json.dumps([{"symbol": {"value": "http://swarm.os/symbol/file2.py#Class1"}, "hash": {"value": "old_hash"}}])
        else:
            mock_resp.results_json = json.dumps([])
        return mock_resp

    mock_indexer.stub.QuerySparql.side_effect = mock_query_sparql_per_file

    # Simulate _process_file fallback behavior
    for uri in file_uris:
        rel_path = uri.split("/")[-1]
        preloaded = batch_hashes.get(uri) if batch_hashes is not None else None

        # Internally _process_file falls back to _get_existing_hashes
        if preloaded is not None:
            existing_hashes = preloaded
        else:
            existing_hashes = mock_indexer._get_existing_hashes(uri)

        if rel_path == 'file1.py':
            assert existing_hashes == {'http://swarm.os/symbol/file1.py#func1': 'hash1'}
        elif rel_path == 'file2.py':
            assert existing_hashes == {'http://swarm.os/symbol/file2.py#Class1': 'old_hash'}

    # Expect multiple calls (1 failed batch + 2 per-file)
    assert mock_indexer.stub.QuerySparql.call_count == 3
