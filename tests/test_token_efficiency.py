import unittest
import os
import sys
from unittest.mock import MagicMock, patch

# Add path to lib and agents
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

from llm import LLMService
from analyst import AnalystAgent

class TestTokenEfficiency(unittest.TestCase):

    @patch('llm.OpenAI')
    def test_llm_cache(self, mock_openai):
        """Test that repeated LLM calls hit the cache."""
        # Setup Mock
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Configure the Mock response object to have proper integers for usage
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Mock Response"
        mock_response.choices = [MagicMock(message=mock_message)]

        # IMPORTANT: Mock usage tokens as integers to avoid format error
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 10
        mock_response.usage = mock_usage

        mock_client.chat.completions.create.return_value = mock_response

        # Instantiate LLM Service
        llm = LLMService()
        llm.stub = MagicMock() # Mock Synapse

        # First Call (Miss)
        prompt = "Explain quantum physics"
        res1 = llm.completion(prompt)
        self.assertEqual(res1, "Mock Response")
        # Ensure it was called once
        self.assertEqual(mock_client.chat.completions.create.call_count, 1)

        # Reset Mock calls but keep return value
        mock_client.chat.completions.create.reset_mock()

        # Second Call (Hit)
        res2 = llm.completion(prompt)
        self.assertEqual(res2, "Mock Response")
        # Should NOT call OpenAI again
        # IMPORTANT: Need to check if called with DIFFERENT args or just not called.
        # But wait, we mock the CLIENT, so if cache hits, client method shouldn't be touched.

        # Debugging what is happening: It seems it IS being called.
        # This implies cache key generation or storage is failing.
        # Check LLMService code again.

        # Re-check logic in llm.py
        # cache_key = self._get_cache_key(prompt, system_prompt)
        # if cache_key in self._cache: ...

        # In test, system_prompt defaults.
        # Let's ensure strict equality in test calls.

        mock_client.chat.completions.create.assert_not_called()

    def test_prompt_optimization(self):
        """Test that stop words are removed."""
        analyst = AnalystAgent()
        analyst.llm.stub = MagicMock() # Mock Synapse

        prompt = "The quick brown fox jumps over the lazy dog in the park."
        optimized = analyst.optimize_prompt(prompt)

        # Check expected words are present
        expected_words = ["quick", "brown", "fox", "jumps", "lazy", "dog", "park."]
        for word in expected_words:
            self.assertIn(word, optimized)

        # Check removed words are gone (case-insensitive check logic in implementation)
        # Implementation: if word.lower() not in stop_words
        # "The" -> "the" is in stop words.
        # "over" is in stop words.
        # "in" is in stop words.

        unwanted_words = ["The", "over", "in"]
        for word in unwanted_words:
            # Need to split by whitespace to avoid substring matches
            self.assertNotIn(word, optimized.split())

        # Verify length reduction
        self.assertLess(len(optimized), len(prompt))

if __name__ == '__main__':
    unittest.main()
