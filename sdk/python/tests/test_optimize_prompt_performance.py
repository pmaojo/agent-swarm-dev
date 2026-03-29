import time
import pytest
from sdk.python.agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()

    # Create a large dummy prompt with many spaces and newlines
    large_prompt = "    def dummy_func():\n        " + " ".join(["var_" + str(i) for i in range(100)]) + " = 1\n\n\n\n\n\n"
    large_prompt = large_prompt * 100

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(large_prompt)
    duration = time.time() - start_time

    print(f"\n100 iterations of optimize_prompt took {duration:.4f} seconds.")
    assert duration < 1.0, f"Performance test failed: took {duration:.4f}s, expected < 1.0s"
