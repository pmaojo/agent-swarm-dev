import unittest
from unittest.mock import MagicMock
import os
import sys
import json

# Add path hacks
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents', 'proto'))

# Mock dependencies
sys.modules['semantic_engine_pb2'] = MagicMock()
sys.modules['semantic_engine_pb2_grpc'] = MagicMock()

from orchestrator import OrchestratorAgent

class TestKillSwitch(unittest.TestCase):
    def setUp(self):
        os.environ["OPENAI_API_KEY"] = "sk-dummy"
        # Prevent connect() from failing
        OrchestratorAgent.connect = MagicMock()
        OrchestratorAgent.load_schema = MagicMock()
        OrchestratorAgent.load_security_policy = MagicMock()
        OrchestratorAgent.load_consolidated_wisdom = MagicMock()
        self.orch = OrchestratorAgent()
        self.orch.stub = MagicMock()

    def test_running_default(self):
        # ASK returns False (Not Halted)
        mock_response = MagicMock()
        mock_response.results_json = json.dumps({"boolean": False})
        self.orch.stub.QuerySparql.return_value = mock_response

        status = self.orch.check_operational_status()
        self.assertEqual(status, "OPERATIONAL")

    def test_halted_shadowing(self):
        # ASK returns True (Halted exists without later Operational)
        mock_response = MagicMock()
        mock_response.results_json = json.dumps({"boolean": True})
        self.orch.stub.QuerySparql.return_value = mock_response

        status = self.orch.check_operational_status()
        self.assertEqual(status, "HALTED")

if __name__ == "__main__":
    unittest.main()
