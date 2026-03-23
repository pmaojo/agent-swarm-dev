import time
import pytest
import sys
import os

SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

def test_optimize_prompt_performance():
    from agents.analyst import AnalystAgent
    analyst = AnalystAgent()

    # Create a reasonably large prompt to amplify regex overhead
    base_prompt = """
    This is   a   test prompt


    with   multiple      spaces

    and  newlines.

    def my_func():
        # Keep space indentation
        return True

\tdef my_tab_func():
\t\t# Keep tab indentation
\t\treturn False
    """
    large_prompt = base_prompt * 100

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(large_prompt)
    elapsed = time.time() - start_time

    assert elapsed < 1.0, f"Performance regression: optimize_prompt took {elapsed:.2f}s, expected < 1.0s"
