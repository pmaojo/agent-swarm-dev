import time
import pytest
from sdk.python.agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
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
    """ * 10  # Make it a bit longer

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    duration = time.time() - start_time

    # Performance assertion: 100 iterations should take less than 1.0s
    assert duration < 1.0, f"Performance regression: optimize_prompt took {duration}s for 100 iterations"
