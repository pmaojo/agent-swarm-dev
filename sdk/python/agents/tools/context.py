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

# Import CodeGraph Slicer
try:
    from lib.code_graph_slicer import CodeGraphSlicer
except ImportError:
    CodeGraphSlicer = None

# Import Synapse gRPC
try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        # Fallback for some environments
        try:
            from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
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
        self.slicer = CodeGraphSlicer() if CodeGraphSlicer else None
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

    def _hybrid_search(self, query_text: str) -> str:
        """Fallback Hybrid Search for 'Intuition Mode'."""
        if not self.stub or not semantic_engine_pb2:
            return ""

        try:
            # Determine Hybrid Mode
            # Prefer SearchMode.HYBRID if available, otherwise use value 2
            hybrid_mode = 2
            if hasattr(semantic_engine_pb2, 'SearchMode'):
                if hasattr(semantic_engine_pb2.SearchMode, 'HYBRID'):
                    hybrid_mode = semantic_engine_pb2.SearchMode.HYBRID
                elif hasattr(semantic_engine_pb2.SearchMode, 'Value'):
                    try:
                        hybrid_mode = semantic_engine_pb2.SearchMode.Value('HYBRID')
                    except Exception:
                        pass
            elif hasattr(semantic_engine_pb2, 'HYBRID'):
                hybrid_mode = semantic_engine_pb2.HYBRID

            request = semantic_engine_pb2.HybridSearchRequest(
                query=query_text,
                namespace="default",
                vector_k=5,
                graph_depth=2,
                mode=hybrid_mode,
                limit=5
            )
            response = self.stub.HybridSearch(request)

            if not response.results:
                return ""

            # Filter and Format
            # Threshold: 0.65
            results_text = "\n\n### 🌌 Ecos de la Forja (Intuición de Synapse):\n"
            found_any = False

            for result in response.results:
                if result.score >= 0.65:
                    found_any = True
                    results_text += f"- [Related] {result.content} (Afinidad: {result.score:.2f})\n"

            return results_text if found_any else ""

        except Exception as e:
            print(f"⚠️ [ContextParser] Hybrid Search Error: {e}")
            return ""

    def _get_file_knowledge(self, filename: str, context_text: str = "") -> str:
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

        if results:
            knowledge = "\n\n### Synapse Knowledge & Constraints:\n"
            for r in results:
                rule_text = r.get("rule", {}).get("value", "")
                rule_type = r.get("type", {}).get("value", "Rule")
                if rule_text:
                    knowledge += f"- [{rule_type}] {rule_text}\n"
            return knowledge

        # Fallback: Intuition Mode (Hybrid Search)
        # Query = Filename + Context Snippet
        # We take first 200 chars of context to capture intent
        snippet = context_text[:200].replace('\n', ' ')
        search_query = f"{filename} {snippet}".strip()
        return self._hybrid_search(search_query)

    def expand_context(self, text: str) -> str:
        """
        Parses @file:path and @symbol:name, injecting content + Synapse knowledge.
        Uses CodeGraphSlicer for @symbol (Skeleton View).
        """
        expanded_text = text + "\n\n--- Context ---\n"
        has_expansions = False

        # 1. Handle @symbol:name (Surgical Slicing)
        symbol_pattern = r'@symbol:([\w\.]+)'
        symbol_matches = re.findall(symbol_pattern, text)

        for symbol_name in symbol_matches:
            has_expansions = True
            if self.slicer:
                # Resolve symbol URI
                # Heuristic: Find symbol URI ending with symbol_name
                # We need a SPARQL query to find it.
                uri = self._resolve_symbol_uri(symbol_name)
                if uri:
                    result = self.slicer.get_pruned_context(uri)
                    context_code = result.get("context", "")
                    savings = result.get("savings_percent", 0.0)

                    expanded_text += f"\n### CodeGraph Slice: {symbol_name} (Savings: {savings:.1f}%)\n{context_code}\n"
                else:
                    expanded_text += f"\n[Warning] Symbol '{symbol_name}' not found in CodeGraph.\n"
            else:
                 expanded_text += f"\n[Warning] CodeGraph Slicer not available for '{symbol_name}'.\n"

        # 2. Handle @file:path (Full Content)
        file_pattern = r'@file:([\w\./\-_]+)'
        file_matches = re.findall(file_pattern, text)

        for filename in file_matches:
            has_expansions = True
            # 1. Read File Content
            content = read_file(filename)

            # 2. Fetch Synapse Knowledge
            knowledge = self._get_file_knowledge(filename, text)

            expanded_text += f"\nFile: {filename}\n```\n{content}\n```\n{knowledge}\n"

        return expanded_text if has_expansions else text

    def _resolve_symbol_uri(self, symbol_name: str) -> str:
        """Finds a symbol URI by name suffix."""
        if not self.stub:
            return ""

        # Try exact match on qualified name suffix
        # URI format: .../symbol/{path}#{qname}
        # Regex filter might be slow, but for now ok.
        query = f"""
        PREFIX swarm: <{SWARM}>
        SELECT ?s WHERE {{
            ?s a <http://swarm.os/ontology/codegraph/CodeNode> .
            FILTER(STRENDS(STR(?s), "#{symbol_name}"))
        }}
        LIMIT 1
        """

        results = self._query_synapse(query)
        if results:
            return results[0].get("s", {}).get("value", "")
        return ""

if __name__ == "__main__":
    # Test
    parser = ContextParser()
    test_input = "Please check @file:README.md and fix issues."
    print(parser.expand_context(test_input))
