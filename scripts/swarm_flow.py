#!/usr/bin/env python3
"""
End-to-End Swarm Flow
Connects all agents via Orchestrator's Advanced Reasoning (Graph-based State Machine)
"""
import os
import sys
import json
import argparse
from typing import Dict, Any, Optional

# Add agents to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

from orchestrator import OrchestratorAgent

class SwarmFlow:
    def __init__(self, use_memory: bool = True):
        self.orchestrator = OrchestratorAgent()
        
    def log(self, agent: str, message: str):
        print(f"📝 [{agent}] {message}")
        
    def run(self, task: str) -> Dict[str, Any]:
        """Execute the full swarm flow"""
        self.log("Orchestrator", f"Starting advanced reasoning flow for: {task}")
        
        # The Orchestrator now manages the entire flow internally via Graph reasoning
        # so we just delegate to it.
        result = self.orchestrator.run(task)
        
        self.log("Swarm", f"✅ Workflow Complete")
        
        # Extract deployment URL if present in history
        deployment_url = "N/A"
        for step in result.get("history", []):
            if step.get("agent") == "Deployer" and step.get("result", {}).get("status") == "success":
                deployment_url = step.get("result", {}).get("url", "N/A")

        result["url"] = deployment_url
        return result

def main():
    parser = argparse.ArgumentParser(description="Run Agent Swarm")
    parser.add_argument("task", nargs="*", default=["Create a simple API"], help="Task description")
    parser.add_argument("--no-memory", action="store_true", help="Disable memory (Deprecated: Orchestrator always uses Synapse now)")
    args = parser.parse_args()
    
    task = " ".join(args.task)
    flow = SwarmFlow(use_memory=True)
    
    print(f"\n🚀 Starting Swarm Flow (Graph-Driven)")
    print(f"📋 Task: {task}\n")
    
    result = flow.run(task)
    
    print(f"\n{'='*50}")
    print(f"✅ Deployment URL: {result.get('url', 'N/A')}")
    print(f"📊 Steps Executed: {len(result.get('history', []))}")
    
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
