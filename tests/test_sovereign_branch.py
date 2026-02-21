import unittest
import os
import sys
import uuid
import json
from unittest.mock import MagicMock, patch

# Add path to lib and agents
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

from git_service import GitService
from cloud_gateways.factory import CloudGatewayFactory
from orchestrator import OrchestratorAgent

class TestSovereignBranch(unittest.TestCase):

    @patch('git_service.subprocess.run')
    def test_branch_creation_ingestion(self, mock_subprocess):
        """Test if creating a branch triggers Synapse Ingestion."""
        # Mock Synapse connection
        mock_stub = MagicMock()

        with patch('git_service.semantic_engine_pb2_grpc.SemanticEngineStub', return_value=mock_stub):
            git = GitService()
            git.stub = mock_stub # Force mock

            # Setup subprocess mock
            mock_subprocess.return_value.stdout = "main"
            mock_subprocess.return_value.returncode = 0

            task_id = "task-123"
            branch_name = git.create_branch(task_id, "Coder")

            self.assertIn("feature/task-123", branch_name)

            # Verify IngestTriples was called
            # Check arguments
            self.assertTrue(mock_stub.IngestTriples.called)
            # Inspect payload if possible, but just checking call is enough for smoke test

    def test_cloud_provider_selection(self):
        """Test SPARQL-based provider selection logic."""
        mock_stub = MagicMock()

        factory = CloudGatewayFactory()
        factory.stub = mock_stub

        # Mock Query Response: Claude is best for Python
        mock_response = MagicMock()
        mock_response.results_json = json.dumps([
            {"providerUri": "http://swarm.os/ontology/provider/Claude", "lat": "2.5"}
        ])
        mock_stub.QuerySparql.return_value = mock_response

        provider = factory.get_best_provider("python")
        self.assertEqual(provider.name(), "Claude")

    @patch('orchestrator.OrchestratorAgent.connect')
    @patch('orchestrator.OrchestratorAgent.load_schema')
    @patch('orchestrator.OrchestratorAgent.load_security_policy')
    @patch('orchestrator.OrchestratorAgent.load_consolidated_wisdom')
    def test_orchestrator_mode_detection(self, mock_wisdom, mock_policy, mock_schema, mock_connect):
        """Test detection logic without side effects."""
        orch = OrchestratorAgent()

        mode = orch.detect_mode("Build feature X [MODE:WAR_ROOM]")
        self.assertEqual(mode, "PARALLEL")

        mode = orch.detect_mode("Review design [MODE:COUNCIL]")
        self.assertEqual(mode, "TABLE_ORDER")

if __name__ == '__main__':
    unittest.main()
