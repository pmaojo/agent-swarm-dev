import unittest
from unittest.mock import MagicMock
import os
import sys
import json
import importlib

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

# Ensure we import fresh LLMService
if 'llm' in sys.modules:
    del sys.modules['llm']
import llm
from llm import LLMService, BudgetExceededException

class TestBudgeting(unittest.TestCase):
    def setUp(self):
        # Set low budget and dummy API key
        os.environ["MAX_DAILY_BUDGET"] = "0.0001"
        os.environ["OPENAI_API_KEY"] = "sk-dummy"
        os.environ["MOCK_LLM"] = "false" # Force Real Mode for Logic Testing

        # Reload to pick up env vars if needed (though LLMService reads in __init__)
        self.llm = LLMService()

        # Manually ensure stub is mocked
        self.llm.stub = MagicMock()
        self.llm.channel = MagicMock()

        # Mock OpenAI
        self.llm.client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test Response"))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=100)
        self.llm.client.chat.completions.create.return_value = mock_response

    def test_budget_enforcement(self):
        print("Testing Budget Enforcement with Mocked Synapse...")

        # Mock responses
        resp_zero = MagicMock()
        resp_zero.results_json = json.dumps([{"total": "0.0"}]) # Initially 0

        resp_high = MagicMock()
        resp_high.results_json = json.dumps([{"total": "10.0"}]) # High spend

        # Use a function side_effect to avoid StopIteration issues
        def side_effect(*args, **kwargs):
            side_effect.counter += 1
            # First 2 queries (check_budget, log_spend of first call) return 0
            if getattr(side_effect, 'counter', 0) <= 2:
                return resp_zero
            else:
                return resp_high

        side_effect.counter = 0
        self.llm.stub.QuerySparql.side_effect = side_effect

        # First call (Should Succeed)
        try:
            self.llm.completion("Test prompt")
        except BudgetExceededException:
            self.fail("Budget exceeded prematurely on first call.")

        # Verify IngestTriples was called (logging spend)
        self.assertTrue(self.llm.stub.IngestTriples.called)

        # Second call (Should Fail)
        with self.assertRaises(BudgetExceededException):
            self.llm.completion("Test prompt 2")

        print("✅ BudgetExceededException raised correctly with mocked Synapse.")

if __name__ == "__main__":
    unittest.main()
