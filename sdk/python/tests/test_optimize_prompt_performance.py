import time
from agents.analyst import AnalystAgent

def test_optimize_prompt_performance():
    agent = AnalystAgent()
    prompt = """
    def hello():
        print("hello    world")



    hello()
    """ * 100 # Make it somewhat large

    start = time.time()
    for _ in range(100):
        agent.optimize_prompt(prompt)
    duration = time.time() - start
    print(f"Duration: {duration}")
    assert duration < 1.0
