#!/usr/bin/env python3
import sys
import os

# Ensure root is in path just in case
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from agents.orchestrator import OrchestratorAgent
except ImportError as e:
    print(f"❌ Failed to import OrchestratorAgent: {e}")
    sys.exit(1)

def main():
    print("🤖 Starting Autonomous Swarm Brain...")

    try:
        agent = OrchestratorAgent()
        agent.autonomous_loop()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
