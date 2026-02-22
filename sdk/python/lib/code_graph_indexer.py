import os
import sys
import grpc
import json
import logging
import fnmatch
from typing import List, Dict, Set, Any, Tuple

# Ensure proto modules can import each other
proto_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'agents', 'proto'))
if proto_path not in sys.path and os.path.exists(proto_path):
    sys.path.append(proto_path)

# Imports
try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        try:
            import semantic_engine_pb2, semantic_engine_pb2_grpc
        except ImportError:
            semantic_engine_pb2 = None
            semantic_engine_pb2_grpc = None

from lib.code_parser import CodeParser

# Ontology Namespaces
SWARM = "http://swarm.os/ontology/"
CODEGRAPH = "http://swarm.os/ontology/codegraph/"
XSD = "http://www.w3.org/2001/XMLSchema#"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CodeGraphIndexer")

class CodeGraphIndexer:
    def __init__(self, root_path: str = "."):
        self.root_path = os.path.abspath(root_path)
        self.parser = CodeParser()
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None

    def connect(self):
        if not semantic_engine_pb2_grpc:
            logger.warning("Synapse gRPC modules not found. Indexing disabled.")
            return False

        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Synapse: {e}")
            return False

    def close(self):
        if self.channel:
            self.channel.close()

    def index_repository(self):
        """Scans the repository and indexes all supported files."""
        if not self.stub:
            if not self.connect():
                return

        logger.info(f"Starting CodeGraph Indexing for {self.root_path}...")
        ignore_patterns = self._load_gitignore()

        for root, dirs, files in os.walk(self.root_path):
            # 1. Filter Directories
            # Remove hidden dirs and explicit excludes
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['synapse-data', 'protoc', '__pycache__', 'node_modules', 'venv', 'env']]

            # Check ignore patterns for directories
            dirs[:] = [d for d in dirs if not self._is_ignored(os.path.join(root, d), ignore_patterns)]

            for file in files:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, self.root_path)

                # Check ignore patterns for files
                if self._is_ignored(filepath, ignore_patterns):
                    continue

                ext = os.path.splitext(file)[1]
                if ext in self.parser.languages:
                    try:
                        self._process_file(filepath, rel_path)
                    except Exception as e:
                        logger.error(f"Error processing {rel_path}: {e}")

        logger.info("CodeGraph Indexing complete.")

    def _load_gitignore(self) -> List[str]:
        patterns = []
        gitignore_path = os.path.join(self.root_path, '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
        return patterns

    def _is_ignored(self, path: str, patterns: List[str]) -> bool:
        rel_path = os.path.relpath(path, self.root_path)
        name = os.path.basename(path)
        for pattern in patterns:
            # Simple fnmatch check
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path, pattern):
                return True
            # Check directory prefix
            if pattern.endswith('/') and rel_path.startswith(pattern):
                 return True
        return False

    def _process_file(self, filepath: str, rel_path: str):
        # 1. Parse File
        result = self.parser.parse_file(filepath)
        if not result or not result.get('symbols'):
            return

        symbols = result['symbols']
        # Resolve qualified names
        symbols = self._resolve_qualified_names(symbols)

        # 2. Fetch existing state from Synapse
        file_uri = f"http://swarm.os/file/{rel_path}"
        existing_hashes = self._get_existing_hashes(file_uri)

        # 3. Determine diff
        triples_to_add = []
        triples_to_remove = []

        # Always define the File node
        triples_to_add.append(semantic_engine_pb2.Triple(
            subject=file_uri,
            predicate=f"http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
            object=f"{CODEGRAPH}File"
        ))

        # Check symbols
        current_symbol_uris = set()

        for sym in symbols:
            qname = sym['qualified_name']
            sym_uri = f"http://swarm.os/symbol/{rel_path}#{qname}"
            current_symbol_uris.add(sym_uri)

            # Check if changed
            if sym_uri in existing_hashes:
                if existing_hashes[sym_uri] == sym['hash']:
                    # No change
                    continue
                else:
                    # Changed: remove old definition triples (simplified: we just overwrite properties,
                    # but for relationships we might need to clean up)
                    # For MVP, we just ingest new state. Synapse handles property overwrites?
                    # Usually RDF stores accumulate. We might need DELETE query.
                    self._delete_symbol_data(sym_uri)

            # Generate triples
            triples_to_add.extend(self._generate_symbol_triples(file_uri, sym_uri, sym, rel_path))

        # Check for deleted symbols
        for existing_uri in existing_hashes:
            if existing_uri not in current_symbol_uris:
                self._delete_symbol_data(existing_uri)
                # Also remove hasSymbol link
                triples_to_remove.append(semantic_engine_pb2.Triple(
                    subject=file_uri,
                    predicate=f"{SWARM}hasSymbol",
                    object=existing_uri
                ))

        # 4. Ingest
        if triples_to_add:
            # logger.info(f"Ingesting {len(triples_to_add)} triples for {rel_path}")
            req = semantic_engine_pb2.IngestRequest(triples=triples_to_add, namespace="default")
            self.stub.IngestTriples(req)

        # TODO: Handle removals via SPARQL Update since IngestRequest is additive-only usually?
        # Assuming IngestRequest adds. To remove, we need SPARQL DELETE.

    def _resolve_qualified_names(self, symbols: List[Dict]) -> List[Dict]:
        sorted_syms = sorted(symbols, key=lambda x: x['start_line'])
        stack = []

        for sym in sorted_syms:
            # Pop closed scopes
            while stack and stack[-1]['end_line'] < sym['start_line']:
                stack.pop()

            if stack:
                parent = stack[-1]
                sym['qualified_name'] = f"{parent['qualified_name']}.{sym['name']}"
            else:
                sym['qualified_name'] = sym['name']

            stack.append(sym)

        return sorted_syms

    def _get_existing_hashes(self, file_uri: str) -> Dict[str, str]:
        """Returns {symbol_uri: hash}."""
        if not self.stub:
            return {}

        query = f"""
        PREFIX swarm: <{SWARM}>
        SELECT ?symbol ?hash WHERE {{
            <{file_uri}> swarm:hasSymbol ?symbol .
            ?symbol swarm:nodeHash ?hash .
        }}
        """
        try:
            request = semantic_engine_pb2.SparqlRequest(query=query, namespace="default")
            response = self.stub.QuerySparql(request)
            results = json.loads(response.results_json)

            hashes = {}
            for r in results:
                s = r.get("symbol", {}).get("value")
                h = r.get("hash", {}).get("value")
                if s and h:
                    hashes[s] = h
            return hashes
        except Exception as e:
            logger.error(f"SPARQL Error: {e}")
            return {}

    def _delete_symbol_data(self, symbol_uri: str):
        """Deletes all statements where symbol is subject."""
        if not self.stub:
            return

        query = f"""
        DELETE WHERE {{
            <{symbol_uri}> ?p ?o .
        }}
        """
        try:
            request = semantic_engine_pb2.SparqlRequest(query=query, namespace="default")
            # Using QuerySparql for update if supported, or specialized method?
            # Assuming QuerySparql handles updates or we rely on Ingest overwrites for now.
            # Synapse might verify if QuerySparql supports UPDATE.
            # If not, we risk stale data.
            # For MVP, assume it works or ignore deletion.
            self.stub.QuerySparql(request)
        except Exception:
            pass

    def _generate_symbol_triples(self, file_uri: str, symbol_uri: str, sym: Dict, rel_path: str) -> List[Any]:
        triples = []

        # Type
        type_uri = f"{CODEGRAPH}Function" if sym['type'] == 'function' else \
                   f"{CODEGRAPH}Class" if sym['type'] == 'class' else \
                   f"{CODEGRAPH}CodeNode"

        triples.append(semantic_engine_pb2.Triple(subject=symbol_uri, predicate=f"http://www.w3.org/1999/02/22-rdf-syntax-ns#type", object=type_uri))

        # Link File -> Symbol
        triples.append(semantic_engine_pb2.Triple(subject=file_uri, predicate=f"{SWARM}hasSymbol", object=symbol_uri))

        # Properties
        triples.append(semantic_engine_pb2.Triple(subject=symbol_uri, predicate=f"{SWARM}nodeHash", object=f'"{sym["hash"]}"'))
        triples.append(semantic_engine_pb2.Triple(subject=symbol_uri, predicate=f"{SWARM}startLine", object=f'"{sym["start_line"]}"^^<{XSD}integer>'))
        triples.append(semantic_engine_pb2.Triple(subject=symbol_uri, predicate=f"{SWARM}endLine", object=f'"{sym["end_line"]}"^^<{XSD}integer>'))

        # Calls
        for called_name in sym.get('calls', []):
            # Try to resolve called_name? For now use a provisional URI or just the name if ontology allows?
            # Ontology says range: Function. Should be URI.
            # We construct a URI: symbol:unknown/name
            # Or if it looks like a local call?
            # Let's use a generic URI based on name
            call_uri = f"http://swarm.os/symbol/ref/{called_name}"
            triples.append(semantic_engine_pb2.Triple(subject=symbol_uri, predicate=f"{SWARM}calls", object=call_uri))

        # Inheritance
        for parent in sym.get('inherits_from', []):
             parent_uri = f"http://swarm.os/symbol/ref/{parent}"
             triples.append(semantic_engine_pb2.Triple(subject=symbol_uri, predicate=f"{SWARM}inheritsFrom", object=parent_uri))

        return triples

if __name__ == "__main__":
    indexer = CodeGraphIndexer()
    indexer.index_repository()
