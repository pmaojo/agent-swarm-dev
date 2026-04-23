import os
import sys
import grpc
import torch
import numpy as np

# Append SDK path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sdk.python.agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from sdk.python.lib.embeddings import FastEmbedFractal

def main():
    # @synapse:constraint Persistencia Fractal
    # Architectural change: Implemented migration script for Fractal Embeddings.
    # It loops over current nodes in Synapse, computes new Fractal Embeddings
    # and re-ingests them to support the prefix structure of the Two-Stage Ranker.
    host = os.environ.get("SYNAPSE_GRPC_HOST", "localhost")
    port = os.environ.get("SYNAPSE_GRPC_PORT", "50051")
    channel = grpc.insecure_channel(f"{host}:{port}")
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

    # Process all nodes and generate new embeddings traversing current nodes
    for t in triples:
        text = f"{t.subject} {t.predicate} {t.object}"

        # Generate new Fractal Embeddings directly via the fractal projection space
        fractal_embeddings = embedder.embed([text])
        if fractal_embeddings:

            # Create a new Triple with the computed embedding retaining full dimensions,
            # which correctly integrates with the two-stage prefix structure handled by the Rust engine
            new_t = semantic_engine_pb2.Triple(
                subject=t.subject,
                predicate=t.predicate,
                object=t.object,
                provenance=t.provenance,
                embedding=fractal_embeddings[0]
            )
            new_triples.append(new_t)

    print(f"Ingesting {len(new_triples)} triples with new fractal embeddings...")
    ingest_req = semantic_engine_pb2.IngestRequest(triples=new_triples, namespace="default")

    try:
        # Increase limit if batch is too big
        ingest_resp = stub.IngestTriples(ingest_req)
        print(f"Successfully re-ingested triples: {ingest_resp.nodes_added} nodes, {ingest_resp.edges_added} edges.")
    except Exception as e:
        print(f"Failed to ingest triples: {e}")


if __name__ == "__main__":
    main()
