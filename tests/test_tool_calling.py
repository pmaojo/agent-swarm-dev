import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os

# Add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))

# Mock modules before import
sys.modules['agents.proto'] = MagicMock()
sys.modules['proto'] = MagicMock()
sys.modules['synapse.infrastructure.web'] = MagicMock()
sys.modules['semantic_engine_pb2'] = MagicMock()
sys.modules['semantic_engine_pb2_grpc'] = MagicMock()
sys.modules['grpc'] = MagicMock()
sys.modules['requests'] = MagicMock() # Mock requests
sys.modules['llm'] = MagicMock() # Mock llm module

from agents.coder import CoderAgent

class TestToolCalling(unittest.TestCase):
    def setUp(self):
        # Patch grpc constructor or just rely on mocked module
        # Since we mocked grpc, CoderAgent constructor calling grpc.insecure_channel will use mock
        self.agent = CoderAgent()
        self.agent.stub = MagicMock()
        # Mock LLM instance created in constructor
        # self.agent.llm is a mock object from sys.modules['llm'].LLMService()
        self.agent.llm = MagicMock()

    def test_tool_execution(self):
        # 1. Tool Call Message
        mock_msg_tool = MagicMock()
        mock_msg_tool.tool_calls = [MagicMock()]
        mock_msg_tool.tool_calls[0].function.name = "execute_command"
        mock_msg_tool.tool_calls[0].function.arguments = json.dumps({"command": "ls", "reason": "list"})
        mock_msg_tool.tool_calls[0].id = "call_123"
        mock_msg_tool.content = None

        # 2. Final Message
        mock_msg_final = MagicMock()
        mock_msg_final.tool_calls = None
        mock_msg_final.content = "Task Complete"

        # Configure the mock completion method
        self.agent.llm.completion.side_effect = [mock_msg_tool, mock_msg_final]

        # Patch execute_command inside agents.coder
        # This patches 'agents.coder.execute_command' which is the imported function
        with patch('agents.coder.execute_command') as mock_exec:
            mock_exec.return_value = {"status": "success", "stdout": "file.txt"}

            result = self.agent.generate_code_with_verification("List files")

            # Verify result structure
            self.assertEqual(result.get("status"), "success")
            self.assertEqual(result.get("result"), "Task Complete")

            # Verify execute_command called
            mock_exec.assert_called_with("ls", "list")

if __name__ == '__main__':
    unittest.main()
