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
    import time
    from agents.analyst import AnalystAgent
    analyst = AnalystAgent()
    prompt = "    This is   a   test prompt\n\n\nwith   multiple      spaces\n\nand  newlines.\n" * 50

    start = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    duration = time.time() - start

    assert duration < 1.0, f"Performance regression: optimize_prompt took {duration}s for 100 iterations, expected < 1.0s"
