import pytest
import time
import os
import sys

SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

from agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
    analyst.analyst_stub = None # Disable gRPC stub to test local Python logic

    prompt = """
    This is   a   test prompt


    with   multiple      spaces

    and  newlines.

    def my_func():
        # Keep space indentation
        return True

	def my_tab_func():
		# Keep tab indentation
		return False
    """ * 100

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    end_time = time.time()

    elapsed = end_time - start_time
    print(f"Elapsed time: {elapsed:.4f} seconds")
    # TDD Red Phase: we set a tight threshold for optimized fast-path operations
    assert elapsed < 0.5, f"Performance regression: optimize_prompt took {elapsed:.4f} seconds, expected < 0.5s"
