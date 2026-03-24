import time
from unittest.mock import MagicMock
import sys
sys.modules['agents.synapse_proto'] = MagicMock()
sys.modules['agents.synapse_proto.semantic_engine_pb2'] = MagicMock()
sys.modules['agents.synapse_proto.semantic_engine_pb2_grpc'] = MagicMock()

from agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
    prompt = " \t  word1  word2 \n" * 1000

    start = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    duration = time.time() - start

    assert duration < 1.0, f"Performance regression: optimize_prompt took {duration}s for 100 iterations"
