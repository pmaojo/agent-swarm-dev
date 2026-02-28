import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))

sys.modules['semantic_engine_pb2'] = MagicMock()
sys.modules['semantic_engine_pb2_grpc'] = MagicMock()
sys.modules['agents.synapse_proto.codegraph_pb2'] = MagicMock()
sys.modules['agents.synapse_proto.codegraph_pb2_grpc'] = MagicMock()

from sdk.python.lib.code_graph_indexer import CodeGraphIndexer

def test_indexer_batch_optimization():
    indexer = CodeGraphIndexer(root_path=".")
    indexer.stub = MagicMock()

    mock_hashes = {
        "http://swarm.os/file/test1.py": {"http://swarm.os/symbol/test1.py#func1": "hash1"},
        "http://swarm.os/file/test2.py": {"http://swarm.os/symbol/test2.py#func2": "hash2"}
    }

    with patch.object(indexer, '_get_existing_hashes_batch', return_value=mock_hashes) as mock_batch:
        with patch.object(indexer, '_process_file') as mock_process:
            with patch('os.walk', return_value=[('.', [], ['test1.py', 'test2.py'])]):
                indexer.parser.languages = {'.py': MagicMock()}
                indexer.index_repository()

            mock_batch.assert_called_once()
            assert mock_process.call_count == 2
            mock_process.assert_any_call("./test1.py", "test1.py", mock_hashes["http://swarm.os/file/test1.py"])
            mock_process.assert_any_call("./test2.py", "test2.py", mock_hashes["http://swarm.os/file/test2.py"])

def test_indexer_batch_fallback():
    indexer = CodeGraphIndexer(root_path=".")
    indexer.stub = MagicMock()

    with patch.object(indexer, '_get_existing_hashes_batch', return_value=None) as mock_batch:
        with patch.object(indexer, '_process_file') as mock_process:
            with patch('os.walk', return_value=[('.', [], ['test1.py'])]):
                indexer.parser.languages = {'.py': MagicMock()}
                indexer.index_repository()

            mock_batch.assert_called_once()
            # Process should be called with pre_fetched_hashes=None
            mock_process.assert_called_once_with("./test1.py", "test1.py", None)

def test_indexer_batch_query_format():
    indexer = CodeGraphIndexer(root_path=".")
    indexer.stub = MagicMock()

    mock_response = MagicMock()
    mock_response.results_json = '[{"file": {"value": "http://swarm.os/file/f1.py"}, "symbol": {"value": "sym1"}, "hash": {"value": "h1"}}]'
    indexer.stub.QuerySparql.return_value = mock_response

    with patch('sdk.python.lib.code_graph_indexer.semantic_engine_pb2.SparqlRequest') as mock_request:
        result = indexer._get_existing_hashes_batch(["http://swarm.os/file/f1.py"])

        # Verify the SPARQL request had the right syntax
        call_kwargs = mock_request.call_args.kwargs
        query = call_kwargs.get('query', '')

        assert "VALUES ?file { <http://swarm.os/file/f1.py> }" in query
        assert "?file swarm:hasSymbol ?symbol ." in query
        assert "?symbol swarm:nodeHash ?hash ." in query

        # Verify result parsing
        assert result is not None
        assert "http://swarm.os/file/f1.py" in result
        assert result["http://swarm.os/file/f1.py"]["sym1"] == "h1"
