import time
import pytest
from agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
    analyst.analyst_stub = None  # Force local Python fallback

    # A large prompt with lots of whitespace
    prompt = """
    def my_function():
        # This is a very    spaced out    comment
        x = 1      +       2



        return x
    """ * 1000

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    duration = time.time() - start_time

    print(f"Execution time: {duration}s")
    assert duration < 1.0, f"Performance regression! Execution took {duration}s, expected < 1.0s"
