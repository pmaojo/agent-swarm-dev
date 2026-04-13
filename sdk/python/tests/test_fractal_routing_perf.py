import time
import pytest
from unittest.mock import MagicMock
from sdk.python.agents.orchestrator import OrchestratorAgent
from sdk.python.agents.synapse_proto import semantic_engine_pb2

def test_fast_classify_stack_performance():
    # Setup the agent
    agent = OrchestratorAgent()

    # Mock the gRPC stub to simulate a real response without hitting the network
    mock_stub = MagicMock()

    # Create a mock response
    mock_response = semantic_engine_pb2.SearchResponse()
    result1 = mock_response.results.add()
    result1.score = 0.95  # Distance would be 1.0 - 0.95 = 0.05 < 0.2
    result1.uri = "http://swarm.os/stack/python"
    result1.content = "Python development stack"

    mock_stub.HybridSearch.return_value = mock_response
    agent.stub = mock_stub

    start_time = time.time()

    iterations = 100
    for _ in range(iterations):
        result = agent.fast_classify_stack("Implement a REST API")
        assert result == "python"

    end_time = time.time()
    elapsed = end_time - start_time

    # Assert that 100 iterations complete in under 0.5s
    assert elapsed < 0.5, f"fast_classify_stack took {elapsed:.3f}s for 100 iterations, expected < 0.5s"
    print(f"Performance test passed: {elapsed:.3f}s for 100 iterations")
