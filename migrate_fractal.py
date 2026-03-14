import sys
import os
import json
import grpc
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "sdk/python")))

from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from lib.embeddings import FastEmbedFractal

def main():
    print("Initiating Fractal Migration...")
    channel = grpc.insecure_channel("localhost:50051")
    stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)

    # Init fast embed
    embedder = FastEmbedFractal()

    try:
        req = semantic_engine_pb2.EmptyRequest(namespace="default")
        res = stub.GetAllTriples(req)

        triples_to_update = []
        unique_texts = set()
        for t in res.triples:
            text = f"{t.subject} {t.predicate} {t.object}"
            unique_texts.add(text)

        texts_list = list(unique_texts)
        if not texts_list:
            print("No triples found in store to migrate.")
            return

        print(f"Generating fractal embeddings for {len(texts_list)} unique triples...")
        embeddings = embedder.embed(texts_list)
        text_to_embed = dict(zip(texts_list, embeddings))

        for t in res.triples:
            text = f"{t.subject} {t.predicate} {t.object}"
            new_t = semantic_engine_pb2.Triple(
                subject=t.subject,
                predicate=t.predicate,
                object=t.object,
                provenance=t.provenance,
                embedding=text_to_embed[text]
            )
            triples_to_update.append(new_t)

        print("Re-ingesting updated triples into Synapse...")
        ingest_req = semantic_engine_pb2.IngestRequest(triples=triples_to_update, namespace="default")
        stub.IngestTriples(ingest_req)

        print("Fractal Migration complete.")

    except grpc.RpcError as e:
        print(f"Error communicating with Synapse Engine: {e}")

if __name__ == "__main__":
    main()
