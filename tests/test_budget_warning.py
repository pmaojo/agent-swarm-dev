import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import json

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
# Do NOT add agents/proto to prevent real import during mock setup

# Mock modules
sys.modules['semantic_engine_pb2'] = MagicMock()
sys.modules['semantic_engine_pb2_grpc'] = MagicMock()

# Now import LLMService (which will use mocked modules)
from llm import LLMService

class TestBudgetWarning(unittest.TestCase):
    def setUp(self):
        # Set budget to $10.0
        os.environ["MAX_DAILY_BUDGET"] = "10.0"
        os.environ["OPENAI_API_KEY"] = "sk-dummy"
        os.environ["TELEGRAM_BOT_TOKEN"] = "dummy_token"
        os.environ["TELEGRAM_CHAT_ID"] = "dummy_chat"

        self.llm = LLMService()
        self.llm.stub = MagicMock()
        self.llm.channel = MagicMock()

        # Mock requests.post
        self.requests_patcher = patch('requests.post')
        self.mock_post = self.requests_patcher.start()

    def tearDown(self):
        self.requests_patcher.stop()

    def test_warning_trigger(self):
        print("Testing Budget Warning Trigger...")

        # 1. get_daily_spend returns 8.5 (85%)
        # 2. check_budget_warning queries warning status -> [] (Not triggered yet)

        # Mocks for QuerySparql
        resp_spend = MagicMock()
        resp_spend.results_json = json.dumps([{"total": "8.5"}])

        resp_warning = MagicMock()
        resp_warning.results_json = json.dumps([]) # Empty list = not found

        # Side effect for QuerySparql
        # Calls:
        # 1. get_daily_spend -> Query
        # 2. check_budget_warning -> Query (check if warning exists)
        self.llm.stub.QuerySparql.side_effect = [resp_spend, resp_warning]

        # Call check_budget (we mock log_spend or ignore exceptions from completion if we just test check_budget)
        # We can call check_budget directly
        try:
            self.llm.check_budget()
        except Exception as e:
            pass # We don't care about budget exceeded here, just warning

        # Verify Telegram Alert Sent
        self.mock_post.assert_called_once()
        print("✅ Telegram Alert Sent.")

        # Verify IngestTriples called (to log warning)
        self.llm.stub.IngestTriples.assert_called()

    def test_warning_suppression(self):
        print("Testing Budget Warning Suppression...")

        # 1. get_daily_spend returns 9.0 (90%)
        # 2. check_budget_warning queries warning status -> [{"event": "..."}] (Already triggered)

        resp_spend = MagicMock()
        resp_spend.results_json = json.dumps([{"total": "9.0"}])

        resp_warning_found = MagicMock()
        resp_warning_found.results_json = json.dumps([{"event": "http://swarm.os/event/warning/123"}])

        self.llm.stub.QuerySparql.side_effect = [resp_spend, resp_warning_found]

        self.llm.check_budget()

        # Verify Telegram Alert NOT Sent
        self.mock_post.assert_not_called()
        print("✅ Telegram Alert Suppressed.")

if __name__ == "__main__":
    unittest.main()
