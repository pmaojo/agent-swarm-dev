import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add root to path so 'agents' can be imported as module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

# Mock dependencies before import
sys.modules['semantic_engine_pb2'] = MagicMock()
sys.modules['semantic_engine_pb2_grpc'] = MagicMock()

# Patch OrchestratorAgent inside agents.orchestrator
with patch('agents.orchestrator.OrchestratorAgent') as MockOrch:
    # Setup mock instance
    mock_orch_instance = MockOrch.return_value
    mock_orch_instance.agents = {"Coder": {}, "Reviewer": {}}
    mock_orch_instance.check_operational_status.return_value = "OPERATIONAL"
    mock_orch_instance.query_graph.return_value = [{"count": "5"}] # Generic return

    from lib.gateway_runtime import app

from fastapi.testclient import TestClient

class TestGateway(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_status_endpoint(self):
        # We need to ensure fetch_stats calls mock_orch_instance
        # fetch_stats uses global `orch`.
        # Since we imported `app` AFTER patching `OrchestratorAgent`, the global `orch` is the mock instance?
        # Let's verify.

        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check structure
        self.assertIn("status", data)
        self.assertIn("pending_tasks", data)
        self.assertIn("failed_tasks", data)
        self.assertIn("daily_spend", data)
        self.assertIn("budget_utilization", data)
        self.assertIn("active_agents", data)

        # Check values from mock
        self.assertEqual(data["status"], "OPERATIONAL")
        # pending_tasks parses "5" as int -> 5
        self.assertEqual(data["pending_tasks"], 5)

        print("✅ Gateway /status endpoint verified.")

if __name__ == "__main__":
    unittest.main()
