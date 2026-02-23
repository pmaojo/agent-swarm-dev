import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules['semantic_engine_pb2'] = MagicMock()
sys.modules['semantic_engine_pb2_grpc'] = MagicMock()

with patch('agents.orchestrator.OrchestratorAgent') as MockOrch:
    instance = MockOrch.return_value
    instance.agents = {"Coder": {}, "Reviewer": {}}
    instance.check_operational_status.return_value = "OPERATIONAL"
    instance.query_graph.return_value = [{"count": "0"}]
    instance.bridge.get_cards_in_list.return_value = []
    instance.ingest_triples.return_value = None

    import lib.gateway_runtime as gateway_runtime


class RustGatewayDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = os.environ.get("RUST_GATEWAY_URL")

    def tearDown(self) -> None:
        if self.original is None:
            os.environ.pop("RUST_GATEWAY_URL", None)
        else:
            os.environ["RUST_GATEWAY_URL"] = self.original

    def test_forwarding_disabled_without_rust_gateway_url(self) -> None:
        os.environ.pop("RUST_GATEWAY_URL", None)
        self.assertFalse(gateway_runtime._rust_gateway_enabled())

    def test_forwarding_enabled_with_rust_gateway_url(self) -> None:
        os.environ["RUST_GATEWAY_URL"] = "http://localhost:18080"
        self.assertTrue(gateway_runtime._rust_gateway_enabled())

    @patch('lib.gateway_runtime.requests.request')
    def test_forward_json_request_returns_remote_payload(self, request_mock: MagicMock) -> None:
        os.environ["RUST_GATEWAY_URL"] = "http://localhost:18080"
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"system_status": "OPERATIONAL"}
        request_mock.return_value = response

        payload = gateway_runtime._forward_json_request("GET", "/api/v1/game-state")

        self.assertEqual(payload["system_status"], "OPERATIONAL")
        request_mock.assert_called_once_with(
            method="GET",
            url="http://localhost:18080/api/v1/game-state",
            json=None,
            timeout=3.0,
        )

    @patch('lib.gateway_runtime.requests.request')
    def test_forward_json_request_raises_http_exception_on_remote_failure(self, request_mock: MagicMock) -> None:
        os.environ["RUST_GATEWAY_URL"] = "http://localhost:18080"
        response = MagicMock()
        response.status_code = 503
        response.text = "unavailable"
        request_mock.return_value = response

        with self.assertRaises(gateway_runtime.HTTPException) as raised:
            gateway_runtime._forward_json_request("GET", "/api/v1/game-state")

        self.assertEqual(raised.exception.status_code, 503)


    @patch('lib.gateway_runtime.requests.request')
    def test_mission_assignment_endpoint_forwards_to_rust_gateway(self, request_mock: MagicMock) -> None:
        os.environ["RUST_GATEWAY_URL"] = "http://localhost:18080"
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"status": "COMPLETED"}
        request_mock.return_value = response

        client = TestClient(gateway_runtime.app)
        result = client.post("/api/v1/mission/assign", json={"agent_id": "a1", "repo_id": "r1", "task": "ship"})

        self.assertEqual(result.status_code, 200)
        request_mock.assert_called_once_with(
            method="POST",
            url="http://localhost:18080/api/v1/mission/assign",
            json={"agent_id": "a1", "repo_id": "r1", "task": "ship"},
            timeout=3.0,
        )

    @patch('lib.gateway_runtime.requests.request')
    def test_knowledge_docs_endpoint_forwards_to_rust_gateway(self, request_mock: MagicMock) -> None:
        os.environ["RUST_GATEWAY_URL"] = "http://localhost:18080"
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"node_id": "node-1", "documentation": "doc"}
        request_mock.return_value = response

        client = TestClient(gateway_runtime.app)
        result = client.get("/api/v1/knowledge-tree/nodes/node-1/documentation")

        self.assertEqual(result.status_code, 200)
        request_mock.assert_called_once_with(
            method="GET",
            url="http://localhost:18080/api/v1/knowledge-tree/nodes/node-1/documentation",
            json=None,
            timeout=3.0,
        )


if __name__ == '__main__':
    unittest.main()
