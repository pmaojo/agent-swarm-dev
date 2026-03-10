import sys
import os
import time

SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

from analyst import AnalystAgent

def test_optimize_prompt_reduces_whitespace():
    # Instantiate AnalystAgent
    agent = AnalystAgent()

    # Define a prompt with excessive newlines and spaces
    prompt = """
        You are a Data Analyst for an AI Swarm.


        Identify a pattern in these 5 failures for the role 'Tester' working with stack 'python'.
        The failure note is: "AttributeError: 'NoneType' object has no attribute 'get'"

        Create a concise "Golden Rule" (HardConstraint) to prevent this in the future.
        The rule should be a short, imperative sentence (e.g., "Always verify hook order").



        Return ONLY the rule text.
    """

    optimized = agent.optimize_prompt(prompt)

    # Assert that multiple newlines are collapsed
    assert "\n\n\n" not in optimized
    # Assert that leading/trailing whitespaces are stripped
    assert optimized == optimized.strip()
    # It should still contain the original key strings
    assert "You are a Data Analyst" in optimized
    assert "Return ONLY the rule text." in optimized

def test_optimize_prompt_preserves_indentation():
    agent = AnalystAgent()
    prompt = "def hello():\n    print('world')\n\n\n    return True"
    optimized = agent.optimize_prompt(prompt)

    assert "def hello():" in optimized
    assert "    print('world')" in optimized
    assert "    return True" in optimized
    assert "\n\n\n" not in optimized

def test_optimize_prompt_performance():
    agent = AnalystAgent()

    large_prompt = "    Hello world!    \n\n\n" * 1000

    start = time.time()
    optimized = agent.optimize_prompt(large_prompt)
    elapsed = time.time() - start

    assert elapsed < 0.1, f"Optimization took too long: {elapsed} seconds"
    assert "\n\n\n" not in optimized
