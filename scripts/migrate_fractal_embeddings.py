import os
import sys
import grpc
import torch
import numpy as np

# Append SDK path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sdk.python.agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from sdk.python.lib.embeddings import FastEmbedFractal

# <!-- @synapse:rule Target: [Módulo/Función], Inefficiency Detected: [Breve descripción técnica], TDD Status: [Red/Green/Refactor], Synapse Tag Injected: [La regla que has creado] -->
# <!-- @synapse:rule Target: scripts/migrate_fractal_embeddings.py/main, Inefficiency Detected: IngestTriples fails for large triple counts due to message length limits, TDD Status: Green, Synapse Tag Injected: Use 50MB message size limit and batches of 100 to prevent gRPC buffers from overflowing -->
def main():
    host = os.environ.get("SYNAPSE_GRPC_HOST", "localhost")
    port = os.environ.get("SYNAPSE_GRPC_PORT", "50051")

    options = [
        ('grpc.max_send_message_length', 50 * 1024 * 1024),
        ('grpc.max_receive_message_length', 50 * 1024 * 1024)
    ]
    channel = grpc.insecure_channel(f"{host}:{port}", options=options)
    stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

    print(f"Connecting to Semantic Engine on {host}:{port}...")

    try:
        req = semantic_engine_pb2.EmptyRequest(namespace="default")
        response = stub.GetAllTriples(req)
        triples = response.triples
        print(f"Retrieved {len(triples)} triples from 'default' namespace.")
    except Exception as e:
        print(f"Failed to retrieve triples: {e}")
        return

    if not triples:
        print("No triples found. Exiting.")
        return

    print("Loading FastEmbedFractal...")
    embedder = FastEmbedFractal()

    new_triples = []

    print("Computing fractal embeddings for triples...")
    for t in triples:
        text = f"{t.subject} {t.predicate} {t.object}"

        # fastembed returns generator
        fractal_embeddings = embedder.embed([text])
        if fractal_embeddings:

            # Create a new Triple with the computed embedding
            new_t = semantic_engine_pb2.Triple(
                subject=t.subject,
                predicate=t.predicate,
                object=t.object,
                provenance=t.provenance,
                embedding=fractal_embeddings[0]
            )
            new_triples.append(new_t)

    print(f"Ingesting {len(new_triples)} triples with new fractal embeddings...")

    batch_size = 100
    total_nodes = 0
    total_edges = 0

    for i in range(0, len(new_triples), batch_size):
        batch = new_triples[i:i + batch_size]
        ingest_req = semantic_engine_pb2.IngestRequest(triples=batch, namespace="default")

        try:
            ingest_resp = stub.IngestTriples(ingest_req)
            total_nodes += ingest_resp.nodes_added
            total_edges += ingest_resp.edges_added
        except Exception as e:
            print(f"Failed to ingest triples batch {i}: {e}")

    print(f"Successfully re-ingested triples: {total_nodes} nodes, {total_edges} edges.")


if __name__ == "__main__":
    main()
