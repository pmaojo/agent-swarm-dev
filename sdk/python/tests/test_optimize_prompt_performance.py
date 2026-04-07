import time
import pytest
from analyst import AnalystAgent

def test_optimize_prompt_performance():
    # Disable grpc to test only Python logic
    analyst = AnalystAgent()
    analyst.analyst_stub = None

    prompt = """
    def   hello_world():
        print(  "Hello    world!"   )



    #   Test      spaces
    """

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    duration = time.time() - start_time

    print(f"\nExecution time: {duration}s")

    # Assert execution time is under 1.0 seconds for 100 iterations
    assert duration < 1.0, f"Performance regression: optimize_prompt took {duration}s for 100 iterations, expected < 1.0s"
