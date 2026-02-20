#!/usr/bin/env python3
"""
End-to-End Swarm Flow
Connects all agents: Orchestrator → Coder → Reviewer → Deployer
"""
import os
import sys
import json
import argparse
from typing import Dict, Any, Optional

# Add agents to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

from orchestrator import OrchestratorAgent
from coder import CoderAgent
from reviewer import ReviewerAgent
from deployer import DeployerAgent
from memory import MemoryAgent

class SwarmFlow:
    def __init__(self, use_memory: bool = True):
        self.orchestrator = OrchestratorAgent()
        self.coder = CoderAgent()
        self.reviewer = ReviewerAgent()
        self.deployer = DeployerAgent()
        self.memory = MemoryAgent() if use_memory else None
        
    def log(self, agent: str, message: str):
        print(f"📝 [{agent}] {message}")
        
    def run(self, task: str) -> Dict[str, Any]:
        """Execute the full swarm flow"""
        results = {
            "task": task,
            "steps": []
        }
        
        # Step 1: Orchestrator decomposes task
        self.log("Orchestrator", f"Decomposing task: {task}")
        workflow = self.orchestrator.decompose_task(task)
        results["steps"].append({"agent": "orchestrator", "action": "decompose", "workflow": workflow})
        
        # Save to memory
        if self.memory:
            self.memory.add_triple(
                f"task:{hash(task)}",
                "分解",
                json.dumps(workflow)
            )
        
        # Step 2: Coder generates code
        coder_task = workflow[0]["task"] if workflow else task
        self.log("Coder", f"Generating code: {coder_task}")
        code_result = self.coder.run(coder_task)
        results["steps"].append({"agent": "coder", "result": code_result})
        
        if self.memory:
            self.memory.add_triple(
                f"coder:{hash(task)}",
                "generated",
                json.dumps(code_result.get("generated", {}))
            )
        
        # Step 3: Reviewer reviews code
        reviewer_task = workflow[1]["task"] if len(workflow) > 1 else "Review code"
        self.log("Reviewer", f"Reviewing: {reviewer_task}")
        review_result = self.reviewer.run(reviewer_task, code_result.get("generated"))
        results["steps"].append({"agent": "reviewer", "result": review_result})
        
        # Step 4: Deployer deploys
        deployer_task = workflow[2]["task"] if len(workflow) > 2 else "Deploy"
        self.log("Deployer", f"Deploying: {deployer_task}")
        deploy_result = self.deployer.run(deployer_task)
        results["steps"].append({"agent": "deployer", "result": deploy_result})
        
        results["status"] = "success"
        results["url"] = deploy_result.get("deployment", {}).get("url")
        
        self.log("Swarm", f"✅ Complete! Deployed to: {results['url']}")
        
        return results

def main():
    parser = argparse.ArgumentParser(description="Run Agent Swarm")
    parser.add_argument("task", nargs="*", default=["Create a simple API"], help="Task description")
    parser.add_argument("--no-memory", action="store_true", help="Disable memory")
    args = parser.parse_args()
    
    task = " ".join(args.task)
    flow = SwarmFlow(use_memory=not args.no_memory)
    
    print(f"\n🚀 Starting Swarm Flow")
    print(f"📋 Task: {task}\n")
    
    result = flow.run(task)
    
    print(f"\n{'='*50}")
    print(f"✅ Deployment URL: {result.get('url', 'N/A')}")
    
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
