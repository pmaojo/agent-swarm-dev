#!/usr/bin/env python3
import subprocess
import json
import uuid
import sys
import os
import grpc

# Add sdk path for synapse protos
SDK_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))
sys.path.append(SDK_PATH)

try:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    print("❌ Failed to import Synapse protos. Ensure SDK is built.")
    sys.exit(1)

# Ontology
SWARM = "http://swarm.os/ontology/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

class SemanticBridge:
    def __init__(self, host="localhost", port=50051):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)

    def extract_symbols(self, file_path):
        """Runs github/semantic via docker compose to get symbol JSON."""
        print(f"🔍 Analyzing {file_path} via GitHub Semantic...")
        cmd = [
            "docker", "compose", "run", "--rm", "semantic",
            "symbols", "--json", f"/repo/{file_path}"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except Exception as e:
            print(f"❌ Semantic extraction failed for {file_path}: {e}")
            return None

    def transform_to_triples(self, file_path, data):
        """Transforms semantic output to Synapse triples."""
        if not data or "files" not in data or not data["files"]:
            return []
            
        triples = []
        file_uri = f"{SWARM}code/file/{file_path.replace('/', '_')}"
        
        # File Metadata
        triples.append({"subject": file_uri, "predicate": f"{RDF}type", "object": f"{SWARM}CodeFile"})
        triples.append({"subject": file_uri, "predicate": f"{SWARM}path", "object": f'"{file_path}"'})

        for file_data in data["files"]:
            for symbol in file_data.get("symbols", []):
                name = symbol.get("symbol")
                kind = symbol.get("kind")
                line = symbol.get("line")
                
                symbol_uri = f"{file_uri}/{kind}/{name}_{uuid.uuid4().hex[:6]}"
                
                # Symbol Metadata
                triples.append({"subject": symbol_uri, "predicate": f"{RDF}type", "object": f"{SWARM}{kind.capitalize()}"})
                triples.append({"subject": symbol_uri, "predicate": f"{SWARM}name", "object": f'"{name}"'})
                triples.append({"subject": symbol_uri, "predicate": f"{SWARM}definedIn", "object": file_uri})
                triples.append({"subject": symbol_uri, "predicate": f"{SWARM}line", "object": f'"{line}"'})
                
                # Bi-directional link
                triples.append({"subject": file_uri, "predicate": f"{SWARM}contains", "object": symbol_uri})

        return triples

    def ingest(self, triples, namespace="default"):
        if not triples:
            return
        
        pb_triples = [
            semantic_engine_pb2.Triple(subject=t["subject"], predicate=t["predicate"], object=t["object"])
            for t in triples
        ]
        request = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=namespace)
        try:
            self.stub.IngestTriples(request)
            print(f"✅ Successfully ingested {len(triples)} code intelligence nodes.")
        except Exception as e:
            print(f"❌ Synapse ingestion failed: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: ./semantic_bridge.py <file_path>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    bridge = SemanticBridge(
        host=os.getenv("SYNAPSE_GRPC_HOST", "localhost"),
        port=int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
    )
    
    data = bridge.extract_symbols(file_path)
    if data:
        triples = bridge.transform_to_triples(file_path, data)
        bridge.ingest(triples)

if __name__ == "__main__":
    main()
