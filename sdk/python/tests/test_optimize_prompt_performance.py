import time
import pytest

def test_optimize_prompt_performance():
    from agents.analyst import AnalystAgent
    analyst = AnalystAgent()
    analyst.analyst_stub = None

    prompt = """
    This is   a   test prompt


    with   multiple      spaces

    and  newlines.

    def my_func():
        # Keep space indentation
        return True

\tdef my_tab_func():
\t\t# Keep tab indentation
\t\treturn False
    """ * 100  # The memory specifies a performance regression test assert 100 iterations under 0.5s with a 100 multiplier block

    start = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    duration = time.time() - start

    assert duration < 0.5, f"optimize_prompt took {duration}s"
