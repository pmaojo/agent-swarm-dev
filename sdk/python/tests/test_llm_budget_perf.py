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
    service.stub = MagicMock()
    return service

def test_get_daily_spend_perf(llm_service):
    # We will simulate _query response
    llm_service._query = MagicMock(return_value=[{"?total": "1.50"}])

    start = time.time()
    for _ in range(100):
        spend = llm_service.get_daily_spend()
    duration = time.time() - start

    assert spend == 1.50
    # The performance assertion: should be very fast if cached,
    # or at least we assert it calls _query fewer times.
    assert llm_service._query.call_count == 1
