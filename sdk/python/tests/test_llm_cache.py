import os
import time
import pytest
from unittest.mock import MagicMock, patch

from sdk.python.lib.llm import LLMService

@pytest.fixture
def llm_service():
    os.environ["MOCK_LLM"] = "false"
    os.environ["OPENAI_API_KEY"] = "fake-key"
    service = LLMService()

    # Mock the internal OpenAI client
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Cached response"
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=10)
    # We patch litellm.completion below instead of attaching client

    # Mock Synapse connection
    service.stub = MagicMock()

    return service

@patch('sdk.python.lib.llm.litellm.completion')
def test_llm_cache_hits(mock_completion, llm_service):
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Cached response"
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 10}
    mock_completion.return_value = mock_response

    # First call (should hit the API)
    start1 = time.time()
    res1 = llm_service.completion("Hello world", system_prompt="Test")
    duration1 = time.time() - start1

    # Second call (should hit the cache)
    start2 = time.time()
    res2 = llm_service.completion("Hello world", system_prompt="Test")
    duration2 = time.time() - start2

    assert res1 == "Cached response"
    assert res2 == "Cached response"

    # Verify the API was only called once
    mock_completion.assert_called_once()

@patch('sdk.python.lib.llm.litellm.completion')
def test_llm_cache_misses_different_prompt(mock_completion, llm_service):
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Cached response"
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 10}
    mock_completion.return_value = mock_response

    llm_service.completion("Hello world 1", system_prompt="Test")
    llm_service.completion("Hello world 2", system_prompt="Test")

    assert mock_completion.call_count == 2

@patch('sdk.python.lib.llm.litellm.completion')
def test_llm_cache_lru_eviction(mock_completion, llm_service):
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Cached response"
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 10}
    mock_completion.return_value = mock_response

    # Set max size to 2
    llm_service._cache_max_size = 2
    llm_service._cache.clear()

    llm_service.completion("Prompt 1")
    llm_service.completion("Prompt 2")
    llm_service.completion("Prompt 3") # Evicts Prompt 1

    assert len(llm_service._cache) == 2

    # Call Prompt 1 again (should miss cache, API call count goes to 4)
    llm_service.completion("Prompt 1")
    assert mock_completion.call_count == 4
