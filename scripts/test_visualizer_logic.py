import sys
import os
import json
import asyncio

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Add lib and agents explicitly if needed, but root should suffice for `from agents...` imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'agents')))
# Add proto path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'agents', 'proto')))


# Set dummy key for testing
os.environ["OPENAI_API_KEY"] = "sk-dummy"

try:
    from gateway_runtime import fetch_game_state, fetch_graph_nodes
except ImportError:
    # Try alternate import path if run from root
    from lib.gateway_runtime import fetch_game_state, fetch_graph_nodes

def test_visualizer_endpoints():
    print("--- Testing Visualizer Endpoints ---")

    print("\n1. Testing /api/v1/game-state...")
    # Mocking orch query_graph behavior if needed, but we rely on fallback
    game_state = fetch_game_state()

    # Pretty print, but handle non-serializable objects if any
    print(json.dumps(game_state, indent=2, default=str))

    # Assertions
    if "error" not in game_state:
        assert "party" in game_state, "Missing party in game state"
        assert len(game_state["party"]) > 0, "Party list is empty"
        assert "active_quests" in game_state, "Missing active_quests"
        assert "daily_budget" in game_state, "Missing daily_budget"
        print("✅ /api/v1/game-state verified.")
    else:
        print(f"⚠️ /api/v1/game-state returned error: {game_state['error']}")

    print("\n2. Testing /api/v1/graph-nodes...")
    graph_nodes = fetch_graph_nodes()
    print(json.dumps(graph_nodes, indent=2, default=str))

    # Assertions
    assert "elements" in graph_nodes, "Missing elements in graph nodes"
    assert "nodes" in graph_nodes["elements"], "Missing nodes list"
    assert "edges" in graph_nodes["elements"], "Missing edges list"
    print("✅ /api/v1/graph-nodes verified.")

if __name__ == "__main__":
    test_visualizer_endpoints()
