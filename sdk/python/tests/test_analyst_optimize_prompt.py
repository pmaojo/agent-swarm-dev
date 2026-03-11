import os
import sys

# Add path to lib and agents
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

import pytest
from analyst import AnalystAgent

def test_optimize_prompt():
    analyst = AnalystAgent()

    # 1. Normal prompt with no weird spacing
    prompt1 = "def func():\n    return 1"
    assert analyst.optimize_prompt(prompt1) == "def func():\n    return 1"

    # 2. Prompt with extra blank lines and trailing/leading spaces on non-indented lines
    prompt2 = "    def func():   \n\n\n\n        return 1  \n\n\n   "
    # Note: trailing spaces on non-empty lines are usually collapsed.
    # Newlines should be collapsed to max 2.
    optimized2 = analyst.optimize_prompt(prompt2)
    assert "    def func():" in optimized2
    assert "        return 1" in optimized2
    assert "\n\n\n" not in optimized2

    # 3. Prompt with multiple spaces inline that should be collapsed
    prompt3 = "   a   b     c  \n\n\n d  "
    optimized3 = analyst.optimize_prompt(prompt3)
    assert "a b c" in optimized3

    # 4. JSON-like content with many spaces
    prompt4 = "{\n    \"key\":   \"value\"   \n}"
    assert analyst.optimize_prompt(prompt4) == "{\n    \"key\": \"value\"\n}"

    # 5. Just spaces and newlines
    prompt5 = "   \n  \n  "
    assert analyst.optimize_prompt(prompt5).strip() == ""
