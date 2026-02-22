"""
Knowledge Harvesting Tool.
Scans codebase for @synapse:constraint and @synapse:lesson tags and ingests them into Synapse.
"""
import os
import re
import sys
import grpc
import json
import time

# Import Synapse gRPC
try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        try:
            from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
        except ImportError:
            semantic_engine_pb2 = None
            semantic_engine_pb2_grpc = None

# Namespaces
SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"

class KnowledgeHarvester:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        if not semantic_engine_pb2_grpc:
            print("⚠️ [Harvester] Synapse gRPC modules not found. Ingestion disabled.")
            return

        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"⚠️ [Harvester] Failed to connect to Synapse: {e}")

    def close(self):
        if self.channel:
            self.channel.close()

    def scan_file(self, filepath: str) -> list:
        triples = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

                # Regex for @synapse:constraint
                # It handles single line comments starting with // or # or /*
                # But simple regex is easier: just look for the tag anywhere.
                constraints = re.findall(r'@synapse:constraint\s+(.+)', content)
                lessons = re.findall(r'@synapse:lesson\s+(.+)', content)

                if constraints or lessons:
                    # Construct File URI
                    rel_path = os.path.relpath(filepath, start=".")
                    if rel_path.startswith("./"): rel_path = rel_path[2:]
                    file_uri = f"{SWARM}file/{rel_path.replace('/', '_').replace('.', '_')}"

                    # Add file property triple
                    triples.append({
                        "subject": file_uri,
                        "predicate": f"{SWARM}hasProperty",
                        "object": f"{SWARM}prop/path/{rel_path}"
                    })

                    for c in constraints:
                        c_text = c.strip()
                        triples.append({
                            "subject": file_uri,
                            "predicate": f"{NIST}HardConstraint",
                            "object": f'"{c_text}"'
                        })
                        print(f"  Found Constraint in {rel_path}: {c_text[:50]}...")

                    for l in lessons:
                        l_text = l.strip()
                        triples.append({
                            "subject": file_uri,
                            "predicate": f"{SWARM}LessonLearned",
                            "object": f'"{l_text}"'
                        })
                        print(f"  Found Lesson in {rel_path}: {l_text[:50]}...")
        except Exception as e:
            print(f"⚠️ Error reading {filepath}: {e}")
        return triples

    def scan_and_ingest(self, path: str = "."):
        """Scans file or directory for tags and ingests them."""
        print(f"🔍 [Harvester] Scanning {path} for knowledge tags...")

        all_triples = []

        if os.path.isfile(path):
            all_triples.extend(self.scan_file(path))
        else:
            for dirpath, _, filenames in os.walk(path):
                # Skip hidden dirs
                if "/." in dirpath:
                    continue

                for filename in filenames:
                    if filename.startswith('.'): continue
                    filepath = os.path.join(dirpath, filename)
                    all_triples.extend(self.scan_file(filepath))

        if all_triples:
            print(f"✅ [Harvester] Found {len(all_triples)} knowledge items.")
            if self.stub:
                self._ingest(all_triples)
                print(f"🚀 [Harvester] Ingested triples to Synapse.")
            else:
                print(f"ℹ️ [Harvester] Skipped ingestion (No Connection).")
        else:
            print(f"ℹ️ [Harvester] No new knowledge found.")

    def _ingest(self, triples_data):
        """Ingests list of dict triples."""
        pb_triples = []
        for t in triples_data:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))

        try:
            req = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace="default")
            self.stub.IngestTriples(req)
        except Exception as e:
            print(f"❌ [Harvester] Ingestion failed: {e}")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    harvester = KnowledgeHarvester()
    harvester.scan_and_ingest(path)
    harvester.close()
