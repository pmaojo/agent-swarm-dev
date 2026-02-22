import unittest
import os
import sys
import json
import grpc
import time
import importlib
from unittest.mock import MagicMock

# Add agents/proto to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents', 'proto'))

try:
    import semantic_engine_pb2
    import semantic_engine_pb2_grpc
except ImportError:
    # Fallback if generated locally or in different path
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        semantic_engine_pb2 = None

class TestCodeGraph(unittest.TestCase):
    def setUp(self):
        # Ensure we have real modules, not mocks from other tests
        if 'semantic_engine_pb2' in sys.modules and isinstance(sys.modules['semantic_engine_pb2'], MagicMock):
            del sys.modules['semantic_engine_pb2']
        if 'semantic_engine_pb2_grpc' in sys.modules and isinstance(sys.modules['semantic_engine_pb2_grpc'], MagicMock):
            del sys.modules['semantic_engine_pb2_grpc']

        # Reload to get real ones
        global semantic_engine_pb2, semantic_engine_pb2_grpc
        try:
            if 'semantic_engine_pb2' in sys.modules: importlib.reload(sys.modules['semantic_engine_pb2'])
            else: import semantic_engine_pb2

            if 'semantic_engine_pb2_grpc' in sys.modules: importlib.reload(sys.modules['semantic_engine_pb2_grpc'])
            else: import semantic_engine_pb2_grpc
        except ImportError:
            pass

        if not semantic_engine_pb2:
            self.skipTest("Proto not found")

        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
        self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)

    def test_synapse_connection(self):
        try:
            grpc.channel_ready_future(self.channel).result(timeout=5)
            self.assertTrue(True)
        except grpc.FutureTimeoutError:
            self.fail("Synapse not reachable")

    def test_ingest_and_query(self):
        # Ingest a test triple
        subject = "http://test/node"
        triples = [
            semantic_engine_pb2.Triple(
                subject=subject,
                predicate="http://test/pred",
                object='"value"'
            )
        ]
        req = semantic_engine_pb2.IngestRequest(triples=triples, namespace="test")
        try:
            self.stub.IngestTriples(req)
        except grpc.RpcError as e:
            self.fail(f"Ingest failed: {e}")

        # Query it back
        query = f"SELECT ?o WHERE {{ <{subject}> <http://test/pred> ?o }}"
        req_q = semantic_engine_pb2.SparqlRequest(query=query, namespace="test")
        try:
            res = self.stub.QuerySparql(req_q)
            results = json.loads(res.results_json)

            self.assertTrue(len(results) > 0)
            val = results[0].get("?o") or results[0].get("o")
            # Handle potential dict return from JSON result
            if isinstance(val, dict):
                val = val.get("value")
            self.assertEqual(val, "value")
        except grpc.RpcError as e:
            self.fail(f"Query failed: {e}")

if __name__ == '__main__':
    unittest.main()
