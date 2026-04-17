import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from sdk.python.lib.code_parser import CodeParser
from sdk.python.lib.code_graph_slicer import CodeGraphSlicer

def test_code_parser_init_perf():
    start = time.time()
    for _ in range(10):
        cp = CodeParser()
    duration = time.time() - start
    assert duration < 0.5, f"CodeParser initialization too slow: {duration}s"

def test_code_graph_slicer_init_perf():
    start = time.time()
    for _ in range(1):
        slicer = CodeGraphSlicer()
    duration = time.time() - start
    assert duration < 0.5, f"CodeGraphSlicer initialization too slow: {duration}s"
