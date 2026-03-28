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
    """ * 100

    start = time.time()
    for _ in range(100):
        optimized = analyst.optimize_prompt(prompt)
    end = time.time()

    duration = end - start
    print(f"Duration: {duration}s")
    assert duration < 1.0, f"Performance regression in optimize_prompt: {duration}s"
