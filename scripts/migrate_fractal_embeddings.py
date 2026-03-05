#!/usr/bin/env python3
"""
Fractal Persistence Migration Script

Recorre los nodos actuales en Synapse, genera sus nuevos Fractal Embeddings
y los re-ingeste con la nueva estructura de prefijos.
"""

import os
import sys
import json
import grpc

SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents", "synapse_proto"))

from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from embeddings import FastEmbedFractal

class FractalMigrator:
    def __init__(self, host="localhost", port=50052, namespace="default"):
        self.host = host
        self.port = port
        self.namespace = namespace
        self.channel = grpc.insecure_channel(f"{self.host}:{self.port}")
        self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)

        print("Initializing FractalProjectionHead...")
        self.embedder = FastEmbedFractal()

    def fetch_all_triples(self):
        """Fetch all triples from the current namespace."""
        print(f"Fetching all triples from namespace '{self.namespace}'...")
        req = semantic_engine_pb2.EmptyRequest(namespace=self.namespace)
        try:
            res = self.stub.GetAllTriples(req)
            triples = res.triples
            print(f"Retrieved {len(triples)} triples.")
            return triples
        except grpc.RpcError as e:
            print(f"Synapse Engine not reachable at {self.host}:{self.port}. {e}")
            return []

    def migrate(self, batch_size=100):
        """Generates new fractal embeddings and re-ingests triples."""
        triples = self.fetch_all_triples()
        if not triples:
            print("No triples to migrate.")
            return

        print(f"Starting migration for {len(triples)} triples...")

        batches = []
        for i in range(0, len(triples), batch_size):
            batch = triples[i:i + batch_size]
            batches.append(batch)

        total_migrated = 0
        for batch in batches:
            # Reconstruct textual content for embedding (subject predicate object)
            texts = [f"{t.subject} {t.predicate} {t.object}" for t in batch]

            # Generate Fractal Embeddings
            embeddings = self.embedder.embed(texts)

            pb_triples = []
            for t, emb in zip(batch, embeddings):
                # Copy existing triple data but append the new embedding vector
                pb_triple = semantic_engine_pb2.Triple(
                    subject=t.subject,
                    predicate=t.predicate,
                    object=t.object,
                    embedding=emb
                )
                if t.provenance:
                    pb_triple.provenance.source = t.provenance.source
                    pb_triple.provenance.timestamp = t.provenance.timestamp
                    pb_triple.provenance.method = t.provenance.method
                pb_triples.append(pb_triple)

            # Re-ingest
            req = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace)
            try:
                self.stub.IngestTriples(req)
                total_migrated += len(batch)
                print(f"Migrated {total_migrated}/{len(triples)} triples.")
            except grpc.RpcError as e:
                print(f"Failed to ingest batch: {e}")

        print("Fractal Embedding Migration complete!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate Synapse nodes to Fractal Embeddings.")
    parser.add_argument("--host", default=os.getenv("SYNAPSE_GRPC_HOST", "localhost"), help="Synapse gRPC host")
    parser.add_argument("--port", type=int, default=int(os.getenv("SYNAPSE_GRPC_PORT", "50052")), help="Synapse gRPC port")
    parser.add_argument("--namespace", default="default", help="Namespace to migrate")
    args = parser.parse_args()

    migrator = FractalMigrator(host=args.host, port=args.port, namespace=args.namespace)
    migrator.migrate()
