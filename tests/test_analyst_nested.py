
import time
import json
import pytest
from unittest.mock import MagicMock
from agents.analyst import AnalystAgent
import os

def test_cluster_failures_nested():
    original_connect = AnalystAgent.connect
    AnalystAgent.connect = MagicMock()
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "dummy"

    analyst = AnalystAgent()

    failures = []
    # Nested list: note will become [1] which is unhashable
    base_note = json.dumps([[1], 2])
    double_encoded_note = f'"{base_note}"'

    failures.append({
        'role': {'value': 'http://swarm.os/agent/Coder'},
        'note': {'value': double_encoded_note},
        'execId': {'value': f'http://swarm.os/execution/1'},
        'stack': {'value': '"python"'}
    })

    try:
        clusters = analyst.cluster_failures(failures)
        print("Success")
    except TypeError as e:
        print(f"Crashed as expected: {e}")

    AnalystAgent.connect = original_connect

if __name__ == "__main__":
    test_cluster_failures_nested()
