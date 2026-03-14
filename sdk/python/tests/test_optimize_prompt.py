import pytest

def test_optimize_prompt():
    from agents.analyst import AnalystAgent
    analyst = AnalystAgent()

    prompt = """
    This is   a   test prompt


    with   multiple      spaces

    and  newlines.

    def my_func():
        # Keep indentation
        return True
    """

    optimized = analyst.optimize_prompt(prompt)

    assert "This is a test prompt" in optimized
    assert "with multiple spaces" in optimized
    assert "and newlines." in optimized
    assert "def my_func():" in optimized
    assert "    # Keep indentation" in optimized
    assert "    return True" in optimized

    # Check that excessive newlines are reduced
    assert "\n\n\n" not in optimized
