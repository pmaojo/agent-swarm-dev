#!/usr/bin/env python3
import grpc
import re
import sys
import os
import json
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

def parse_triples(filepath):
    triples = []
    pattern = re.compile(r'<([^>]+)>\s+<([^>]+)>\s+<([^>]+)>')

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            match = pattern.match(line)
            if match:
                subject, predicate, obj = match.groups()
                triples.append({
                    "subject": subject.strip(),
                    "predicate": predicate.strip(),
                    "object": obj.strip()
                })
            else:
                print(f"⚠️  Skipping malformed line: {line}")
    return triples

def ingest_knowledge(filepath="organizational_knowledge.txt", namespace="default"):
    triples = parse_triples(filepath)
    if not triples:
        print("❌ No triples found to ingest.")
        return

    client = GrpcClient()
    try:
        client.ingest_triples(triples, namespace=namespace)
        print(f"✅ Ingested {len(triples)} triples from {filepath} into namespace '{namespace}'")
    except Exception as e:
        print(f"❌ Failed to ingest knowledge: {e}")
        sys.exit(1)

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "organizational_knowledge.txt"
    ingest_knowledge(filepath, namespace="default")
