import time
from agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
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
    """

    # Correctness check first
    optimized = analyst.optimize_prompt(prompt)
    assert "This is a test prompt" in optimized
    assert "with multiple spaces" in optimized
    assert "and newlines." in optimized
    assert "def my_func():" in optimized
    assert "    # Keep space indentation" in optimized
    assert "    return True" in optimized
    assert "\tdef my_tab_func():" in optimized
    assert "\t\t# Keep tab indentation" in optimized
    assert "\t\treturn False" in optimized
    assert "\n\n\n" not in optimized

    # Load test for performance
    large_prompt = prompt * 100

    start = time.time()
    for _ in range(100):
        analyst.optimize_prompt(large_prompt)
    duration = time.time() - start

    assert duration < 1.0, f"Performance regression: took {duration}s"
