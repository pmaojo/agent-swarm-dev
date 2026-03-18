import os
import sys
import grpc
import json

# Add path to lib and agents
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc

from embeddings import FastEmbedFractal

def migrate_fractal_embeddings():
    port = os.getenv("SYNAPSE_GRPC_PORT", "50051")
    host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    channel = grpc.insecure_channel(f"{host}:{port}")

    try:
        grpc.channel_ready_future(channel).result(timeout=5)
    except grpc.FutureTimeoutError:
        print(f"Failed to connect to Synapse Semantic Engine at {host}:{port}")
        sys.exit(1)

    stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

    print("Connecting to Semantic Engine...")

    # 1. Get all triples
    req = semantic_engine_pb2.EmptyRequest(namespace="default")
    try:
        response = stub.GetAllTriples(req)
        triples = response.triples
    except Exception as e:
        print(f"Error calling GetAllTriples: {e}")
        sys.exit(1)

    if not triples:
        print("No triples found to migrate.")
        sys.exit(0)

    print(f"Retrieved {len(triples)} triples. Initializing FastEmbedFractal...")

    embedder = FastEmbedFractal()

    batch_size = 100
    for i in range(0, len(triples), batch_size):
        batch = triples[i:i+batch_size]
        texts_to_embed = [f"{t.subject} {t.predicate} {t.object}" for t in batch]

        print(f"Processing batch {i//batch_size + 1}/{(len(triples) + batch_size - 1)//batch_size}...")
        embeddings = embedder.embed(texts_to_embed)

        # Ingest updated triples
        new_triples = []
        for t, emb in zip(batch, embeddings):
            t_new = semantic_engine_pb2.Triple(
                subject=t.subject,
                predicate=t.predicate,
                object=t.object,
                embedding=emb
            )
            if t.HasField('provenance'):
                t_new.provenance.CopyFrom(t.provenance)
            new_triples.append(t_new)

        ingest_req = semantic_engine_pb2.IngestRequest(
            triples=new_triples,
            namespace="default"
        )

        try:
            stub.IngestTriples(ingest_req)
        except Exception as e:
            print(f"Error during ingestion of batch: {e}")

    print("Migration of Fractal Embeddings completed.")

if __name__ == "__main__":
    migrate_fractal_embeddings()
