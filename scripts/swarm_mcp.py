#!/usr/bin/env python3
"""
MCP Server for Agent Swarm Control
Exposes swarm tools via JSON-RPC stdio
"""
import sys
import json
import os

# Add agents to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

from orchestrator import OrchestratorAgent
from coder import CoderAgent
from reviewer import ReviewerAgent
from deployer import DeployerAgent
from memory import MemoryAgent

class SwarmMCP:
    def __init__(self):
        self.orchestrator = OrchestratorAgent()
        self.coder = CoderAgent()
        self.reviewer = ReviewerAgent()
        self.deployer = DeployerAgent()
        self.memory = MemoryAgent()
        
    def run_agent(self, agent: str, task: str) -> dict:
        """Run a specific agent"""
        if agent == "orchestrator":
            return self.orchestrator.run(task)
        elif agent == "coder":
            return self.coder.run(task)
        elif agent == "reviewer":
            return self.reviewer.run(task)
        elif agent == "deployer":
            return self.deployer.run(task)
        else:
            return {"error": f"Unknown agent: {agent}"}
    
    def run_swarm(self, task: str) -> dict:
        """Run full swarm flow"""
        results = {"task": task, "steps": []}
        
        workflow = self.orchestrator.decompose_task(task)
        results["steps"].append({"agent": "orchestrator", "workflow": workflow})
        
        code_result = self.coder.run(workflow[0]["task"] if workflow else task)
        results["steps"].append({"agent": "coder", "result": code_result})
        
        review_result = self.reviewer.run("Review code", code_result.get("generated"))
        results["steps"].append({"agent": "reviewer", "result": review_result})
        
        deploy_result = self.deployer.run("Deploy")
        results["steps"].append({"agent": "deployer", "result": deploy_result})
        
        results["url"] = deploy_result.get("deployment", {}).get("url")
        return results
    
    def query_memory(self, sparql: str = None, action: str = "get_all", **kwargs) -> dict:
        """Query or update memory"""
        if action == "get_all":
            return self.memory.run("get_all", limit=kwargs.get("limit", 100))
        elif action == "query":
            return self.memory.run("query", sparql=sparql)
        elif action == "add":
            return self.memory.run("add", subject=kwargs["subject"], predicate=kwargs["predicate"], object=kwargs["object"])
        return {"error": f"Unknown action: {action}"}

# MCP Protocol
def handle_request(request: dict) -> dict:
    method = request.get("method")
    params = request.get("params", {})
    id = request.get("id")
    
    mcp = SwarmMCP()
    
    try:
        if method == "run_agent":
            result = mcp.run_agent(params["agent"], params["task"])
        elif method == "run_swarm":
            result = mcp.run_swarm(params["task"])
        elif method == "query_memory":
            result = mcp.query_memory(**params)
        else:
            result = {"error": f"Unknown method: {method}"}
    except Exception as e:
        result = {"error": str(e)}
    
    return {"jsonrpc": "2.0", "id": id, "result": result}

def main():
    """Read JSON-RPC requests from stdin"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            continue

if __name__ == "__main__":
    main()
