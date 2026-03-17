import pytest

def test_optimize_prompt():
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
    """

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

    # Check that excessive newlines are reduced
    assert "\n\n\n" not in optimized

def test_optimize_prompt_performance():
    from agents.analyst import AnalystAgent
    import time
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
    """

    # Pre-warm
    analyst.optimize_prompt(prompt)

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)

    end_time = time.time()
    duration = end_time - start_time
    assert duration < 1.0, f"Performance test failed: took {duration}s"
