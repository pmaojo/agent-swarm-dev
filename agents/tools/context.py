"""
Context Parser & Synapse Integration.
Parses @file and @symbol tags and enriches context with Synapse knowledge.
"""
import os
import re
import sys
import grpc
import json
from typing import Dict, List, Any, Tuple

# Import Tools
try:
    from tools.files import read_file
except ImportError:
    from agents.tools.files import read_file

# Import Synapse gRPC
try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        # Fallback for some environments
        try:
            from proto import semantic_engine_pb2, semantic_engine_pb2_grpc
        except ImportError:
            semantic_engine_pb2 = None
            semantic_engine_pb2_grpc = None

# Namespaces
SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"

class ContextParser:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        if not semantic_engine_pb2_grpc:
            print("⚠️ [ContextParser] Synapse gRPC modules not found. Context will be limited.")
            return

        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"⚠️ [ContextParser] Failed to connect to Synapse: {e}")

    def close(self):
        if self.channel:
            self.channel.close()

    def _query_synapse(self, sparql_query: str) -> List[Dict]:
        """Executes a SPARQL query against Synapse."""
        if not self.stub:
            return []

        try:
            request = semantic_engine_pb2.SparqlRequest(query=sparql_query, namespace="default")
            response = self.stub.QuerySparql(request)
            return json.loads(response.results_json)
        except Exception as e:
            print(f"⚠️ [ContextParser] SPARQL Query Error: {e}")
            return []

    def _get_file_knowledge(self, filename: str) -> str:
        """Fetches constraints and lessons learned for a file/stack."""
        if not self.stub:
            return ""

        # Determine stack/extension
        ext = os.path.splitext(filename)[1].replace('.', '')
        stack_uri = f"http://swarm.os/stack/{ext}"

        # Query for HardConstraints on the stack and the specific file
        # We use UNION to get both general stack rules and specific file rules
        query = f"""
        PREFIX swarm: <{SWARM}>
        PREFIX nist: <{NIST}>

        SELECT ?rule ?type WHERE {{
            {{
                <{stack_uri}> nist:HardConstraint ?rule .
                BIND("Stack Rule" AS ?type)
            }}
            UNION
            {{
                ?s swarm:hasProperty <{SWARM}prop/path/{filename}> .
                ?s nist:HardConstraint ?rule .
                BIND("File Rule" AS ?type)
            }}
            UNION
            {{
                ?s swarm:hasProperty <{SWARM}prop/path/{filename}> .
                ?s swarm:LessonLearned ?rule .
                BIND("Lesson Learned" AS ?type)
            }}
        }}
        """

        results = self._query_synapse(query)

        if not results:
            return ""

        knowledge = "\n\n### Synapse Knowledge & Constraints:\n"
        for r in results:
            rule_text = r.get("rule", {}).get("value", "")
            rule_type = r.get("type", {}).get("value", "Rule")
            if rule_text:
                knowledge += f"- [{rule_type}] {rule_text}\n"

        return knowledge

    def expand_context(self, text: str) -> str:
        """
        Parses @file:path and injects content + Synapse knowledge.
        TODO: Implement @symbol:name parsing.
        """
        # Regex for @file:path
        file_pattern = r'@file:([\w\./\-_]+)'

        matches = re.findall(file_pattern, text)
        if not matches:
            return text

        expanded_text = text + "\n\n--- Context ---\n"

        for filename in matches:
            # 1. Read File Content
            content = read_file(filename)

            # 2. Fetch Synapse Knowledge
            knowledge = self._get_file_knowledge(filename)

            expanded_text += f"\nFile: {filename}\n```\n{content}\n```\n{knowledge}\n"

        return expanded_text

if __name__ == "__main__":
    # Test
    parser = ContextParser()
    test_input = "Please check @file:README.md and fix issues."
    print(parser.expand_context(test_input))
