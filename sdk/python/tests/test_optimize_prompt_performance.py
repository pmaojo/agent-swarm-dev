import time
import os
import sys

# Add path to lib and agents
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

from analyst import AnalystAgent

def test_optimize_prompt_performance():
    agent = AnalystAgent()
    prompt = """
        This   is   a    test


        with   many    spaces
    """ * 1000 # make it VERY long

    start = time.time()
    for _ in range(100):
        agent.optimize_prompt(prompt)
    duration = time.time() - start
    print(f"Duration: {duration}s")
    assert duration < 1.0, f"Performance regression: optimize_prompt took {duration}s (limit: 1.0s)"

if __name__ == '__main__':
    test_optimize_prompt_performance()
