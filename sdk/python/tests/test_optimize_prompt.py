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

    # Create a very large prompt
    large_prompt = "    This is a test line with   multiple   spaces.\n" * 10000

    start_time = time.time()
    optimized = analyst.optimize_prompt(large_prompt)
    end_time = time.time()

    duration = end_time - start_time
    print(f"Optimization took {duration:.4f} seconds")

    # It should be extremely fast, definitely under 0.5s for 10k lines
    assert duration < 0.5, f"Optimization is too slow: {duration:.4f}s"
