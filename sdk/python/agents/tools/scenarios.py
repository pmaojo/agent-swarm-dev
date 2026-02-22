"""
Scenario Loading Tool.
Loads domain-specific ontologies/scenarios from the `scenarios/` directory into Synapse.
"""
import os
import json
import sys
import grpc
import rdflib

# --- Synapse/Proto Imports ---
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if SDK_PYTHON_PATH not in sys.path:
    sys.path.insert(0, SDK_PYTHON_PATH)
    sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
    sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        semantic_engine_pb2 = None
        semantic_engine_pb2_grpc = None

SWARM = "http://swarm.os/ontology/"

class ScenarioLoader:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        if not semantic_engine_pb2_grpc:
            print("⚠️ [ScenarioLoader] Synapse gRPC modules not found.")
            return

        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"⚠️ [ScenarioLoader] Failed to connect to Synapse: {e}")

    def close(self):
        if self.channel:
            self.channel.close()

    def load_scenario(self, scenario_name: str):
        """Loads a scenario from the `scenarios/` directory."""
        scenario_path = os.path.join("scenarios", scenario_name)
        manifest_path = os.path.join(scenario_path, "manifest.json")

        if not os.path.exists(manifest_path):
            print(f"❌ [ScenarioLoader] Scenario '{scenario_name}' not found at {scenario_path}.")
            return False

        print(f"📂 [ScenarioLoader] Loading scenario '{scenario_name}'...")
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            ontologies = manifest.get("ontologies", [])
            for ontology_file in ontologies:
                ontology_path = os.path.join(scenario_path, "schema", ontology_file)
                # Check if it exists in schema/ or root
                if not os.path.exists(ontology_path):
                     ontology_path = os.path.join(scenario_path, ontology_file)

                if os.path.exists(ontology_path):
                    self._ingest_ontology(ontology_path)
                else:
                    print(f"⚠️ [ScenarioLoader] Ontology file '{ontology_file}' missing.")

            print(f"✅ [ScenarioLoader] Scenario '{scenario_name}' loaded successfully.")
            return True
        except Exception as e:
            print(f"❌ [ScenarioLoader] Error loading scenario: {e}")
            return False

    def _ingest_ontology(self, filepath: str):
        """Parses ontology file using rdflib and ingests triples."""
        if not semantic_engine_pb2:
            print("    ⚠️ Synapse protobufs missing. Skipping ingestion.")
            return

        print(f"  > Ingesting ontology: {filepath}")
        g = rdflib.Graph()
        try:
            # Guess format
            fmt = "xml" if filepath.endswith(".owl") else "turtle"
            g.parse(filepath, format=fmt)

            pb_triples = []
            for s, p, o in g:
                # Convert rdflib terms to strings
                subj = str(s)
                pred = str(p)
                obj = str(o)

                # Format object string for literals (add quotes if not URI)
                if isinstance(o, rdflib.Literal):
                    # Handle typing if possible, for now just string literal
                    obj = f'"{obj}"'
                elif not obj.startswith("http") and not obj.startswith("_:"):
                    # Relative URI? Treat as literal if unsure or append base?
                    # For safety, treat as literal if it looks like one
                    pass

                pb_triples.append(semantic_engine_pb2.Triple(
                    subject=subj,
                    predicate=pred,
                    object=obj
                ))

            if self.stub and pb_triples:
                # Chunking if needed, but for now send all
                req = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace="default")
                self.stub.IngestTriples(req)
                print(f"    - Ingested {len(pb_triples)} triples.")

        except Exception as e:
            print(f"    ❌ Failed to parse/ingest {filepath}: {e}")

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "core"
    loader = ScenarioLoader()
    loader.load_scenario(name)
    loader.close()
