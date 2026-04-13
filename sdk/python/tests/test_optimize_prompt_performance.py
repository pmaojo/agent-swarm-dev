import time
import pytest
from agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
    analyst.analyst_stub = None # Disable gRPC stub to test Python logic

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
    """ * 100 # Make it a bit larger

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    elapsed = time.time() - start_time

    print(f"Elapsed time: {elapsed} seconds")
    assert elapsed < 0.5, f"Performance regression: optimize_prompt took {elapsed}s, expected < 0.5s"
