import time
import pytest
import os
import sys

# Ensure proper imports for pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agents")))
from analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
    analyst.analyst_stub = None  # disable gRPC stub

    prompt = """
    This is a   test prompt
    with      multiple spaces.



    And multiple newlines.
    """ * 100 # Make it somewhat large

    start = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    elapsed = time.time() - start

    assert elapsed < 0.5, f"Performance regression: optimize_prompt took {elapsed:.2f}s"

def test_optimize_prompt_correctness():
    analyst = AnalystAgent()
    analyst.analyst_stub = None

    prompt = "    Indented   text\n\n\n\nMore   text"
    expected = "Indented text\n\nMore text"

    assert analyst.optimize_prompt(prompt) == expected

def test_optimize_prompt_whitespace_only():
    analyst = AnalystAgent()
    analyst.analyst_stub = None

    prompt = "    "
    expected = ""
    assert analyst.optimize_prompt(prompt) == expected

def test_optimize_prompt_empty():
    analyst = AnalystAgent()
    analyst.analyst_stub = None

    prompt = ""
    expected = ""
    assert analyst.optimize_prompt(prompt) == expected
