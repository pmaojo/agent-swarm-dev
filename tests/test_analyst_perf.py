
import time
import json
import pytest
import os
from unittest.mock import MagicMock
from agents.analyst import AnalystAgent

def test_cluster_failures_performance():
    # Patch connect so we don't need real Synapse
    original_connect = AnalystAgent.connect
    AnalystAgent.connect = MagicMock()

    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "dummy"

    analyst = AnalystAgent()

    failures = []
    # Make a huge array to force full parsing
    huge_array = ["Error"] + ["Info"] * 10000
    base_note = json.dumps(huge_array)
    double_encoded_note = f'"{base_note}"'

    for i in range(100): # Reduce count to not explode memory, focus on CPU per item
        failures.append({
            'role': {'value': 'http://swarm.os/agent/Coder'},
            'note': {'value': double_encoded_note},
            'execId': {'value': f'http://swarm.os/execution/{i}'},
            'stack': {'value': '"python"'}
        })

    start_time = time.time()
    clusters = analyst.cluster_failures(failures)
    end_time = time.time()

    duration = end_time - start_time
    # Normalize to 10k items equivalent for comparison
    projected_10k = (duration / 100) * 10000
    print(f"Processed {len(failures)} huge JSON arrays in {duration:.4f} seconds (Projected 10k: {projected_10k:.4f}s)")

    assert len(clusters) == 1
    AnalystAgent.connect = original_connect

if __name__ == "__main__":
    test_cluster_failures_performance()
