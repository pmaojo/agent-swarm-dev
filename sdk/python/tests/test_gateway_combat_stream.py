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

    from lib.gateway_runtime import app, combat_event_queue


class CombatStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_combat_stream_receives_published_event(self) -> None:
        combat_event_queue.put_nowait({
            "type": "BUG_SPAWNED",
            "payload": {"type": "BUG_SPAWNED", "message": "spawn", "details": {}, "severity": "WARNING", "timestamp": "t"},
        })

        with self.client.websocket_connect('/api/v1/events/combat/stream') as websocket:
            message = websocket.receive_json()

        self.assertEqual(message["type"], "BUG_SPAWNED")


if __name__ == '__main__':
    unittest.main()
