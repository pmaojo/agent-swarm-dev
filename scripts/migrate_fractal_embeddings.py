import os
import sys
import grpc
import json
from dotenv import load_dotenv

SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc

from embeddings import FastEmbedFractal

def main():
    load_dotenv(os.path.join(SDK_PYTHON_PATH, '..', '..', '.env'))
    grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))

    # Needs a bigger payload limit for batch ingestion
    options = [
        ('grpc.max_send_message_length', 50 * 1024 * 1024),
        ('grpc.max_receive_message_length', 50 * 1024 * 1024)
    ]

    print(f"Connecting to Semantic Engine at {grpc_host}:{grpc_port}...")
    channel = grpc.insecure_channel(f"{grpc_host}:{grpc_port}", options=options)
    stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

    print("Fetching all triples...")
    try:
        req = semantic_engine_pb2.EmptyRequest(namespace="default")
        res = stub.GetAllTriples(req)
        triples = res.triples
        print(f"Fetched {len(triples)} triples.")
    except Exception as e:
        print(f"Failed to fetch triples: {e}")
        return

    if not triples:
        print("No triples to migrate.")
        return

    print("Initializing Fractal Embedding Model...")
    embedder = FastEmbedFractal()

    print("Recomputing fractal embeddings...")

    batch_size = 50
    updated_triples = []

    for i in range(0, len(triples), batch_size):
        batch = triples[i:i+batch_size]
        texts_to_embed = [f"{t.subject} {t.predicate} {t.object}" for t in batch]
        try:
            embeddings = embedder.embed(texts_to_embed)
            for t, emb in zip(batch, embeddings):
                updated_triple = semantic_engine_pb2.Triple(
                    subject=t.subject,
                    predicate=t.predicate,
                    object=t.object,
                    provenance=t.provenance,
                    embedding=emb
                )
                updated_triples.append(updated_triple)
        except Exception as e:
            print(f"Error computing embeddings for batch {i}: {e}")

    print(f"Re-ingesting {len(updated_triples)} triples with fractal embeddings...")
    try:
        ingest_req = semantic_engine_pb2.IngestRequest(triples=updated_triples, namespace="default")
        ingest_res = stub.IngestTriples(ingest_req)
        print(f"Successfully re-ingested. Nodes added/updated: {ingest_res.nodes_added}, Edges: {ingest_res.edges_added}")
    except Exception as e:
        print(f"Failed to re-ingest: {e}")

if __name__ == "__main__":
    main()
