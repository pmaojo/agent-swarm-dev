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
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Cached response"
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=10)
    mock_client.chat.completions.create.return_value = mock_response
    service.client = mock_client

    # Mock Synapse connection
    service.stub = MagicMock()

    return service

def test_llm_cache_hits(llm_service):
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
    llm_service.client.chat.completions.create.assert_called_once()

def test_llm_cache_misses_different_prompt(llm_service):
    llm_service.completion("Hello world 1", system_prompt="Test")
    llm_service.completion("Hello world 2", system_prompt="Test")

    assert llm_service.client.chat.completions.create.call_count == 2

def test_llm_cache_lru_eviction(llm_service):
    # Set max size to 2
    llm_service._cache_max_size = 2
    llm_service._cache.clear()

    llm_service.completion("Prompt 1")
    llm_service.completion("Prompt 2")
    llm_service.completion("Prompt 3") # Evicts Prompt 1

    assert len(llm_service._cache) == 2

    # Call Prompt 1 again (should miss cache, API call count goes to 4)
    llm_service.completion("Prompt 1")
    assert llm_service.client.chat.completions.create.call_count == 4
