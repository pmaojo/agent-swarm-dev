import time
import pytest
from agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
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
    """ * 100  # Make it long enough

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    duration = time.time() - start_time

    assert duration < 1.0, f"Performance regression: took {duration}s"
