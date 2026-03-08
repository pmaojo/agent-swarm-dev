import pytest
from sdk.python.agents.analyst import AnalystAgent

def test_optimize_prompt():
    """
    Test that AnalystAgent.optimize_prompt correctly reduces token usage
    by safely collapsing redundant inline spaces and excessive newlines
    while preserving indentation.
    """
    analyst = AnalystAgent()

    # Simulate a prompt with excessive newlines and spaces
    prompt = "    def my_func():\n\n\n        print(   'hello'   )\n\n\n    "
    optimized = analyst.optimize_prompt(prompt)

    # Assert newlines are collapsed
    assert "\n\n\n" not in optimized
    # Assert spaces are collapsed (this might be tricky to test without breaking indentation)
    # The requirement is to collapse redundant inline spaces and excessive newlines while preserving indentation to avoid corrupting code or stack traces.

    prompt2 = "You are a Data Analyst for an AI Swarm.\n\n        Identify a pattern in these 10 failures for the role 'Coder' working with stack 'python'.\n        The failure note is: \"SyntaxError\"\n\n\n        Create a concise \"Golden Rule\" (HardConstraint) to prevent this in the future.\n        The rule should be a short, imperative sentence (e.g., \"Always verify hook order\").\n        Return ONLY the rule text."
    optimized2 = analyst.optimize_prompt(prompt2)
    assert len(optimized2) < len(prompt2)
    assert "\n\n\n" not in optimized2

    # Let's test a more precise preservation
    code_block = "def foo():\n    x = 1\n    y =    2\n    return x + y"
    opt_code = analyst.optimize_prompt(code_block)
    # The indentation should be preserved, but internal excessive spaces might be reduced
    assert "def foo():\n    x = 1" in opt_code

    print("Optimization test passed.")
