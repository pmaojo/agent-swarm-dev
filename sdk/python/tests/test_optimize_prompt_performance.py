import time
import pytest
from agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
    analyst.analyst_stub = None  # Disable gRPC stub to test local Python logic

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
    elapsed_time = time.time() - start_time

    print(f"Time taken: {elapsed_time}")
    assert elapsed_time < 1.0, f"Performance regression: optimize_prompt took {elapsed_time}s"
