import os
import sys
import grpc

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python', 'agents'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python', 'lib'))

from synapse_proto import semantic_engine_pb2
from synapse_proto import semantic_engine_pb2_grpc
from embeddings import FastEmbedFractal

def migrate_embeddings():
    print("Connecting to Synapse gRPC...")
    options = [
        ('grpc.max_send_message_length', 50 * 1024 * 1024),
        ('grpc.max_receive_message_length', 50 * 1024 * 1024)
    ]
    channel = grpc.insecure_channel('localhost:50051', options=options)
    try:
        grpc.channel_ready_future(channel).result(timeout=5)
        print("✅ Connected to Synapse")
    except grpc.FutureTimeoutError:
        print("❌ Failed to connect to Synapse")
        return

    stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

    print("Fetching all triples...")
    try:
        res = stub.GetAllTriples(semantic_engine_pb2.EmptyRequest(namespace="default"))
        triples = list(res.triples)
        print(f"📦 Received {len(triples)} triples.")
    except Exception as e:
        print(f"❌ Failed to fetch triples: {e}")
        return

    if not triples:
        print("No triples to migrate.")
        return

    embedder = FastEmbedFractal()

    print("Generating Fractal Embeddings...")
    # Extract content for embedding (subject + predicate + object string)
    texts = [f"{t.subject} {t.predicate} {t.object}" for t in triples]
    fractal_embs = embedder.embed(texts)

    print("Re-ingesting updated triples in batches...")
    batch_size = 100
    total_nodes = 0
    total_edges = 0

    for i in range(0, len(triples), batch_size):
        batch = triples[i:i+batch_size]
        batch_embs = fractal_embs[i:i+batch_size]

        new_triples = []
        for t, emb in zip(batch, batch_embs):
            nt = semantic_engine_pb2.Triple(
                subject=t.subject,
                predicate=t.predicate,
                object=t.object,
                provenance=t.provenance,
                embedding=emb
            )
            new_triples.append(nt)

        ingest_req = semantic_engine_pb2.IngestRequest(namespace="default", triples=new_triples)
        try:
            resp = stub.IngestTriples(ingest_req, timeout=30)
            total_nodes += resp.nodes_added
            total_edges += resp.edges_added
            print(f"Ingested batch {i//batch_size + 1}/{(len(triples) + batch_size - 1)//batch_size}...")
        except grpc.RpcError as e:
            print(f"Failed to ingest batch {i//batch_size + 1}: {e}")

    print(f"Migration complete: {total_nodes} nodes, {total_edges} edges added.")

if __name__ == "__main__":
    migrate_embeddings()
