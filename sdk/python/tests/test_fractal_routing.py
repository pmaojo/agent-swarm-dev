import pytest
from sdk.python.agents.orchestrator import OrchestratorAgent
from sdk.python.agents.synapse_proto import semantic_engine_pb2
from unittest.mock import MagicMock
import time

def test_zero_llm_fast_routing():
    """
    Test that fast routing uses the 64d Matryoshka filter to bypass LLM and route tasks directly.
    """
    agent = OrchestratorAgent()

    # Mock the semantic engine stub
    mock_stub = MagicMock()

    # Setup mock response for HybridSearch
    mock_response = semantic_engine_pb2.SearchResponse()
    result = mock_response.results.add()
    result.score = 0.95  # Above 0.8 critical threshold
    result.uri = "http://swarm.org/skill/python"
    result.content = "python backend expert"

    mock_stub.HybridSearch.return_value = mock_response
    agent.stub = mock_stub

    # Time execution
    start_time = time.time()
    handler = agent.get_handler_for_task("Implement a fast backend feature")
    execution_time = time.time() - start_time

    assert handler == "python", f"Expected handler 'python', got '{handler}'"
    assert execution_time < 0.5, f"Expected routing < 0.5s, took {execution_time}s"

    # Assert that HybridSearch was called with prefix_len=64
    mock_stub.HybridSearch.assert_called_once()
    args, kwargs = mock_stub.HybridSearch.call_args
    req = args[0]

    assert req.prefix_len == 64, "Expected prefix_len=64 for coarse Matryoshka filtering"
    assert req.mode == semantic_engine_pb2.SearchMode.VECTOR_ONLY, "Expected VECTOR_ONLY mode"

    # Now verify fallback logic when fast router returns None (below threshold)
    mock_response_fail = semantic_engine_pb2.SearchResponse()
    result_fail = mock_response_fail.results.add()
    result_fail.score = 0.3  # Below 0.8 critical threshold
    result_fail.uri = "http://swarm.org/skill/unknown"
    mock_stub.HybridSearch.return_value = mock_response_fail

    # It should fallback to Rust orchestrator engine or default
    handler_fallback = agent.get_handler_for_task("Some random design task")
    assert handler_fallback != "unknown"  # Should use standard routing mechanism
