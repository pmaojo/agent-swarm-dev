import os
import sys
import json
import grpc
from typing import Dict, Any, List, Optional
from .interfaces import CloudProviderInterface
from .providers import JulesProvider, ClaudeProvider, CodexProvider

# Synapse Setup (Duplicated a bit, but necessary for independence)
current_dir = os.path.dirname(os.path.abspath(__file__))
proto_dir = os.path.join(current_dir, '..', '..', 'agents', 'proto')
if proto_dir not in sys.path:
    sys.path.insert(0, proto_dir)

try:
    import semantic_engine_pb2
    import semantic_engine_pb2_grpc
except ImportError:
    # Try alternate path
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        semantic_engine_pb2 = None
        semantic_engine_pb2_grpc = None

SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

class CloudGatewayFactory:
    def __init__(self):
        self.providers = {
            "Jules": JulesProvider(),
            "Claude": ClaudeProvider(),
            "Codex": CodexProvider()
        }
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.connect_synapse()
        self.ensure_provider_stats()

    def connect_synapse(self):
        if not semantic_engine_pb2_grpc: return
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"⚠️  CloudGateway failed to connect to Synapse: {e}")

    def _ingest(self, triples: List[Dict[str, str]], namespace: str = "default"):
        if not self.stub or not semantic_engine_pb2: return
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        request = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=namespace)
        try:
            self.stub.IngestTriples(request)
        except Exception as e:
            print(f"❌ Ingest failed: {e}")

    def ensure_provider_stats(self):
        """Bootstrap provider stats if missing."""
        # For demo purposes, we ingest specialty and latency
        triples = [
            # Claude: Good at Python/Refactor, Higher Latency
            {"subject": f"{SWARM}provider/Claude", "predicate": f"{SWARM}specialty", "object": '"python"'},
            {"subject": f"{SWARM}provider/Claude", "predicate": f"{SWARM}specialty", "object": '"refactor"'},
            {"subject": f"{SWARM}provider/Claude", "predicate": f"{SWARM}avgLatency", "object": '"2.5"'}, # Seconds

            # Codex: Good at Rust/Migration, Lower Latency
            {"subject": f"{SWARM}provider/Codex", "predicate": f"{SWARM}specialty", "object": '"rust"'},
            {"subject": f"{SWARM}provider/Codex", "predicate": f"{SWARM}specialty", "object": '"migration"'},
            {"subject": f"{SWARM}provider/Codex", "predicate": f"{SWARM}avgLatency", "object": '"1.2"'},

            # Jules: Generalist/Orchestration, Medium Latency
            {"subject": f"{SWARM}provider/Jules", "predicate": f"{SWARM}specialty", "object": '"orchestration"'},
            {"subject": f"{SWARM}provider/Jules", "predicate": f"{SWARM}avgLatency", "object": '"1.8"'}
        ]
        self._ingest(triples)

    def serialize_job_bundle(self, task_description: str, branch_name: str, context: str, rules: List[str]) -> Dict[str, Any]:
        """
        Create a standardized JobBundle for external delegation.
        """
        return {
            "task_description": task_description,
            "branch_name": branch_name,
            "context": context,
            "golden_rules": rules,
            "timestamp": str(os.times()) # Simple timestamp
        }

    def get_best_provider(self, stack: str = "python") -> CloudProviderInterface:
        """
        Selects the best provider based on specialty (stack) and latency.
        """
        if not self.stub:
            return self.providers["Claude"] # Default fallback

        # SPARQL Query as requested
        # SELECT ?providerUri WHERE { ?providerUri swarm:specialty "stack" . ?providerUri swarm:avgLatency ?lat } ORDER BY ?lat

        stack_literal = f'"{stack.lower()}"'
        query = f"""
        PREFIX swarm: <{SWARM}>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT ?providerUri ?lat
        WHERE {{
            ?providerUri swarm:specialty {stack_literal} .
            ?providerUri swarm:avgLatency ?lat .
        }}
        ORDER BY ASC(xsd:decimal(?lat))
        LIMIT 1
        """

        request = semantic_engine_pb2.SparqlRequest(query=query, namespace="default")
        try:
            response = self.stub.QuerySparql(request)
            results = json.loads(response.results_json)

            if results:
                provider_uri = results[0].get("?providerUri") or results[0].get("providerUri")
                if provider_uri:
                    name = provider_uri.split('/')[-1]
                    if name in self.providers:
                        print(f"🎯 Selected Provider: {name} (Stack: {stack})")
                        return self.providers[name]

            print(f"⚠️  No specialist found for {stack}, using default.")
            return self.providers["Claude"]

        except Exception as e:
            print(f"❌ Provider selection failed: {e}")
            return self.providers["Claude"]

    def track_success_per_dollar(self) -> str:
        """
        Returns the SPARQL query to track Success-per-Dollar ratio.
        """
        return """
        PREFIX swarm: <http://swarm.os/ontology/>
        SELECT ?provider (COUNT(?task) / SUM(?cost) as ?ratio)
        WHERE {
            ?task swarm:handledBy ?provider .
            ?task swarm:status "SUCCESS" .
            ?task swarm:cost ?cost .
        }
        GROUP BY ?provider
        """
