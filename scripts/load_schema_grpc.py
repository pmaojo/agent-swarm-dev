#!/usr/bin/env python3
import yaml
import sys
import grpc
import os
from typing import List, Dict

# Add lib path for synapse sdk
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))
from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc

class GrpcClient:
    def __init__(self, host="localhost", port=50051):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)

    def ingest_triples(self, triples: List[Dict[str, str]], namespace: str = "default"):
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))

        request = semantic_engine_pb2.IngestRequest(
            triples=pb_triples,
            namespace=namespace
        )
        return self.stub.IngestTriples(request)

def load_schema(filepath="swarm_schema.yaml", namespace="default"):
    with open(filepath, 'r') as f:
        schema = yaml.safe_load(f)

    triples = []

    # Agents
    for agent_name, agent_data in schema.get('agents', {}).items():
        subject = f"http://swarm.os/agent/{agent_name}"
        triples.append({"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/Agent"})
        triples.append({"subject": subject, "predicate": "http://swarm.os/description", "object": agent_data.get('description', '')})

    # Tasks
    for task_name, task_data in schema.get('tasks', {}).items():
        subject = f"http://swarm.os/task/{task_name}"
        triples.append({"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/TaskType"})
        triples.append({"subject": subject, "predicate": "http://swarm.os/handler", "object": f"http://swarm.os/agent/{task_data.get('handler')}"})
        triples.append({"subject": subject, "predicate": "http://swarm.os/description", "object": task_data.get('description', '')})

    # Transitions
    for task_name, transitions in schema.get('transitions', {}).items():
        subject = f"http://swarm.os/task/{task_name}"
        if transitions.get('on_success'):
            triples.append({"subject": subject, "predicate": "http://swarm.os/on_success", "object": f"http://swarm.os/task/{transitions.get('on_success')}"})
        if transitions.get('on_failure'):
            triples.append({"subject": subject, "predicate": "http://swarm.os/on_failure", "object": f"http://swarm.os/task/{transitions.get('on_failure')}"})

    client = GrpcClient()
    try:
        client.ingest_triples(triples, namespace=namespace)
        print(f"✅ Loaded {len(triples)} triples from {filepath} into namespace '{namespace}'")
    except Exception as e:
        print(f"❌ Failed to load schema: {e}")
        sys.exit(1)

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "swarm_schema.yaml"
    load_schema(filepath, namespace="default")
