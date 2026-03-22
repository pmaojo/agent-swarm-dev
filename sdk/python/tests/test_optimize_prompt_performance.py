import pytest
import time

def test_optimize_prompt_performance():
    from agents.analyst import AnalystAgent
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
    """ * 10

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    end_time = time.time()

    duration = end_time - start_time
    assert duration < 1.0, f"Execution took {duration}s, which is longer than the 1.0s limit"
