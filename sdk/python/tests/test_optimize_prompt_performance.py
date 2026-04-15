import time
import pytest
from sdk.python.agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
    analyst.analyst_stub = None  # Force python implementation

    prompt = """
        def test_func():
            #   Lots of    spaces
            x = 1


            y = 2



            return x + y
    """

    start = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    elapsed = time.time() - start

    assert elapsed < 0.5, f"optimize_prompt took too long: {elapsed}s"
