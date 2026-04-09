import time
import pytest

def test_optimize_prompt_performance():
    from agents.analyst import AnalystAgent
    analyst = AnalystAgent()
    # Force mock_llm just in case
    analyst.mock_llm = True

    # disable the stub to test python side code
    analyst.analyst_stub = None

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

    execution_time = end_time - start_time
    assert execution_time < 1.0, f"Execution time {execution_time}s exceeded limit of 1.0s"
