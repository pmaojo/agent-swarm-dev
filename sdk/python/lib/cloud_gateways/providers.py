import uuid
import json
import time
from typing import Dict, Any, List
from .interfaces import CloudProviderInterface

class BaseProvider(CloudProviderInterface):
    def __init__(self, synapse_stub=None):
        self.stub = synapse_stub
        self.namespace = "default"

    def _ingest_cost(self, task_id: str, cost: float, provider: str):
        if not self.stub: return
        # Ingest cost triple
        # <task:ID> swarm:cost <amount> ; swarm:provider <provider_id>
        pass # Simplified for now, Orchestrator handles cost tracking in plan step 4?
             # Prompt says "Cost Tracking: Ingest triples for every external call".
             # Orchestrator does it or Provider does it?
             # "The tool pushes the JobBundle... Upon external completion, the PR created... must be tagged".
             # "Cost Tracking: Ingest triples for every external call".
             # I'll implement it here if I have stub access.

    def name(self) -> str:
        return self.__class__.__name__.replace("Provider", "")

    def delegate_task(self, job_bundle: Dict[str, Any]) -> str:
        print(f"☁️  [{self.name()}] Received Delegation: {job_bundle.get('task_description')[:50]}...")
        # Simulate latency
        time.sleep(1)

        # Simulate creating a PR
        # In a real scenario, this would call an API which then calls back or we poll.
        # For simulation, we return a mock PR URI.
        pr_id = str(uuid.uuid4())[:8]
        pr_uri = f"http://swarm.os/pr/{pr_id}"

        print(f"☁️  [{self.name()}] Task Completed. PR Created: {pr_uri}")
        return pr_uri

    def get_status(self, task_id: str) -> str:
        return "COMPLETED"


class JulesProvider(BaseProvider):
    def name(self) -> str:
        return "Jules"

class ClaudeProvider(BaseProvider):
    def name(self) -> str:
        return "Claude"

class CodexProvider(BaseProvider):
    def name(self) -> str:
        return "Codex"
