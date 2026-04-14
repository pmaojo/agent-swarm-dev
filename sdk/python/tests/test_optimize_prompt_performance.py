import time
from agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    analyst = AnalystAgent()
    analyst.analyst_stub = None # ensure it uses python backend

    prompt_base = "    This is   a   test prompt\n\n\n    with   multiple      spaces\n\n    and  newlines.\n"
    prompt = prompt_base * 100

    # Assert correctness
    single_optimized = analyst.optimize_prompt(prompt_base)
    assert "This is a test prompt" in single_optimized
    assert "with multiple spaces" in single_optimized
    assert "and newlines." in single_optimized
    assert "\n\n\n" not in single_optimized

    start_time = time.time()
    for _ in range(100):
        analyst.optimize_prompt(prompt)
    duration = time.time() - start_time

    print(f"Optimize prompt 100 iterations duration: {duration:.4f}s")
    assert duration < 0.5, f"Performance regression! duration: {duration:.4f}s"
