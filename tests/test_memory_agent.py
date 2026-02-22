import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import grpc

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python')))

from agents.memory import MemoryAgent, MemoryAgentError


class FakeRpcError(grpc.RpcError):
    pass


class TestMemoryAgent(unittest.TestCase):
    def test_invalid_namespace_raises_value_error(self):
        with self.assertRaises(ValueError):
            MemoryAgent(namespace="   ")

    @patch("agents.memory.semantic_engine_pb2_grpc.SemanticEngineStub")
    @patch("agents.memory.grpc.insecure_channel")
    def test_connect_success_sets_channel_and_stub(self, mock_channel, mock_stub_cls):
        channel = object()
        stub = object()
        mock_channel.return_value = channel
        mock_stub_cls.return_value = stub

        agent = MemoryAgent(host="localhost:50051", namespace="swarm")
        agent.connect()

        self.assertIs(agent.channel, channel)
        self.assertIs(agent.stub, stub)

    @patch("agents.memory.grpc.insecure_channel", side_effect=FakeRpcError("down"))
    def test_connect_rpc_error_wrapped(self, _mock_channel):
        agent = MemoryAgent()

        with self.assertRaises(MemoryAgentError) as exc:
            agent.connect()

        self.assertIn("Connection failed", str(exc.exception))

    def test_add_triple_success_returns_true(self):
        stub = MagicMock()
        stub.IngestTriples.return_value = MagicMock(edges_added=1)
        agent = MemoryAgent(namespace="swarm")
        agent.stub = stub

        result = agent.add_triple("s", "p", "o")

        self.assertTrue(result)
        stub.IngestTriples.assert_called_once()

    def test_add_triple_rpc_error_wrapped(self):
        stub = MagicMock()
        stub.IngestTriples.side_effect = FakeRpcError("boom")
        agent = MemoryAgent(namespace="swarm")
        agent.stub = stub

        with self.assertRaises(MemoryAgentError) as exc:
            agent.add_triple("s", "p", "o")

        self.assertIn("add_triple failed", str(exc.exception))

    def test_query_success_returns_json_list(self):
        stub = MagicMock()
        stub.QuerySparql.return_value = MagicMock(results_json='[{"s":"a"}]')
        agent = MemoryAgent(namespace="swarm")
        agent.stub = stub

        result = agent.query("SELECT * WHERE {?s ?p ?o}")

        self.assertEqual(result, [{"s": "a"}])

    def test_query_invalid_json_wrapped(self):
        stub = MagicMock()
        stub.QuerySparql.return_value = MagicMock(results_json='not-json')
        agent = MemoryAgent(namespace="swarm")
        agent.stub = stub

        with self.assertRaises(MemoryAgentError) as exc:
            agent.query("SELECT * WHERE {?s ?p ?o}")

        self.assertIn("query failed", str(exc.exception))

    def test_get_all_success_limited(self):
        triple1 = MagicMock(subject="s1", predicate="p1", object="o1")
        triple2 = MagicMock(subject="s2", predicate="p2", object="o2")
        triple3 = MagicMock(subject="s3", predicate="p3", object="o3")
        stub = MagicMock()
        stub.GetAllTriples.return_value = MagicMock(triples=[triple1, triple2, triple3])
        agent = MemoryAgent(namespace="swarm")
        agent.stub = stub

        result = agent.get_all(limit=2)

        self.assertEqual(
            result,
            [{"s": "s1", "p": "p1", "o": "o1"}, {"s": "s2", "p": "p2", "o": "o2"}],
        )

    def test_get_all_rpc_error_wrapped(self):
        stub = MagicMock()
        stub.GetAllTriples.side_effect = FakeRpcError("boom")
        agent = MemoryAgent(namespace="swarm")
        agent.stub = stub

        with self.assertRaises(MemoryAgentError) as exc:
            agent.get_all()

        self.assertIn("get_all failed", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
