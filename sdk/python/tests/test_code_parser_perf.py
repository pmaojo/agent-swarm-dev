
import os
import time
import pytest
import tempfile
from sdk.python.lib.code_parser import CodeParser

@pytest.fixture
def complex_python_file():
    content = """
class Base:
    def base_method(self):
        pass

class Derived(Base):
    def derived_method(self):
        self.base_method()
        print("Hello")

def standalone_func():
    d = Derived()
    d.derived_method()

import os
import sys
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
        tmp.write(content)
        tmp.flush()
        filepath = tmp.name

    yield filepath

    os.remove(filepath)

def test_parser_performance_and_correctness(complex_python_file):
    parser = CodeParser()

    # Measure performance
    start_time = time.time()
    iterations = 100

    for _ in range(iterations):
        parser.parse_file(complex_python_file)

    end_time = time.time()
    duration = end_time - start_time

    print(f"\\nPerformance: {iterations} iterations took {duration:.4f} seconds")

    # Verify correctness
    result = parser.parse_file(complex_python_file)
    symbols = result.get('symbols', [])

    symbol_names = {s['name'] for s in symbols}
    assert 'Base' in symbol_names
    assert 'Derived' in symbol_names
    assert 'base_method' in symbol_names
    assert 'derived_method' in symbol_names
    assert 'standalone_func' in symbol_names

    # Check inheritance
    derived_sym = next(s for s in symbols if s['name'] == 'Derived')
    assert 'Base' in derived_sym.get('inherits_from', [])

    # Check calls
    derived_method_sym = next(s for s in symbols if s['name'] == 'derived_method')
    assert 'base_method' in derived_method_sym.get('calls', [])
