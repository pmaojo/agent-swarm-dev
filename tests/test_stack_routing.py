import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Set dummy API key before imports to avoid OpenAI init error
os.environ['OPENAI_API_KEY'] = 'dummy'

# Add agents/ and lib/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
# Add agents/proto to path to fix grpc imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents', 'proto'))

# Import agents after path setup
from orchestrator import OrchestratorAgent
from analyst import AnalystAgent

class TestStackRouting(unittest.TestCase):

    @patch('orchestrator.grpc.insecure_channel')
    @patch('orchestrator.semantic_engine_pb2_grpc.SemanticEngineStub')
    def test_orchestrator_stack_context(self, mock_stub_class, mock_channel):
        # Mock Stub
        mock_stub = mock_stub_class.return_value

        # Instantiate Orchestrator
        orch = OrchestratorAgent()
        # Mock agents
        orch.agents = {
            "Coder": MagicMock(),
            "Reviewer": MagicMock(),
            "Deployer": MagicMock()
        }

        # Test get_agent_lessons with stack
        # Expected query should contain stack literal
        orch.query_graph = MagicMock(return_value=[])
        orch.get_agent_lessons("Coder", stack="python")

        args, _ = orch.query_graph.call_args
        query = args[0]
        self.assertIn('swarm:hasStack "python"', query)

        # Test get_golden_rules with stack
        orch.get_golden_rules("Coder", stack="react")
        args, _ = orch.query_graph.call_args
        query = args[0]
        self.assertIn('<http://swarm.os/stack/react> nist:HardConstraint ?rule', query)

    @patch('analyst.grpc.insecure_channel')
    @patch('analyst.semantic_engine_pb2_grpc.SemanticEngineStub')
    @patch('analyst.OrchestratorAgent') # Mock the Orchestrator used for validation
    def test_analyst_validation(self, mock_orch_class, mock_stub_class, mock_channel):
        # Mock Stub
        mock_stub = mock_stub_class.return_value

        # Mock Orchestrator instance
        mock_orch = mock_orch_class.return_value
        mock_orch.run.return_value = {'final_status': 'success'}

        # Instantiate Analyst
        analyst = AnalystAgent()
        analyst.mock_llm = True

        # Mock query_graph response for find_unconsolidated_failures
        # Return 5 failures for python stack
        failures = []
        for i in range(5):
            failures.append({
                'execId': {'value': f'http://exec/{i}'},
                'agent': {'value': 'http://agent/Coder'},
                'role': {'value': 'http://role/FrontendDeveloper'},
                'note': {'value': '"Error: IndentationError"'},
                'stack': {'value': '"python"'}
            })

        # Mock query_graph response:
        # 1. detect_schema_gaps -> [] (No gaps found)
        # 2. find_unconsolidated_failures -> failures
        analyst.query_graph = MagicMock(side_effect=[[], failures])

        # Mock ingest_triples
        analyst.ingest_triples = MagicMock()

        # Run Analyst
        analyst.run()

        # Verify validation was called
        # The prompt generates "Always follow python best practices."
        # The validation should run for stack "python"

        # Check if Orchestrator was called with extra_rules
        args, kwargs = mock_orch.run.call_args
        self.assertEqual(kwargs['stack'], 'python')
        self.assertIn("Always follow python best practices.", kwargs['extra_rules'])

        # Verify Ingestion happened for Stack
        # Check first call to ingest_triples (Rule Ingestion)
        ingest_args = analyst.ingest_triples.call_args_list
        # We expect at least 2 calls: Rule Ingestion, Consolidation
        self.assertTrue(len(ingest_args) >= 2)

        rule_triples = ingest_args[0][0][0]
        # Depending on how ingest_triples is called, it might be a list of triples or single
        # The code does: self.ingest_triples(rule_triples) which is a list of dicts

        self.assertEqual(rule_triples[0]['subject'], 'http://swarm.os/stack/python')
        self.assertIn('HardConstraint', rule_triples[0]['predicate'])

if __name__ == '__main__':
    unittest.main()
