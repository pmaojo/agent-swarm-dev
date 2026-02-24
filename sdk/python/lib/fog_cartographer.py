#!/usr/bin/env python3
"""
Fog Cartographer - Maps "Fog of War" coverage and estimates exploration costs.
"""
import os
import sys
import subprocess
import json
import grpc

# Synapse Imports
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SDK_PYTHON_PATH not in sys.path:
    sys.path.insert(0, SDK_PYTHON_PATH)
try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        semantic_engine_pb2 = None
        semantic_engine_pb2_grpc = None

SWARM = "http://swarm.os/ontology/"

class FogCartographer:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        if not semantic_engine_pb2_grpc: return
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"⚠️ Failed to connect to Synapse: {e}")

    def get_tracked_files(self) -> list:
        """Get list of files tracked by git."""
        try:
            res = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
            return res.stdout.splitlines()
        except subprocess.CalledProcessError:
            return []

    def check_synapse_coverage(self, files: list) -> dict:
        """Check which files are indexed in Synapse."""
        if not self.stub:
            return {f: False for f in files}

        # Query for CodeGraph Files
        # URI scheme: http://swarm.os/file/{rel_path}
        query = f"""
        PREFIX codegraph: <http://swarm.os/ontology/codegraph/>
        SELECT ?s WHERE {{ ?s a codegraph:File . }}
        """
        indexed_files = set()
        try:
            res = self.stub.QuerySparql(semantic_engine_pb2.SparqlRequest(query=query, namespace="default"))
            results = json.loads(res.results_json)
            for row in results:
                uri = row.get("?s") or row.get("s")
                if uri:
                    # Extract path from URI: http://swarm.os/file/path/to/file
                    if "http://swarm.os/file/" in uri:
                        path = uri.replace("http://swarm.os/file/", "")
                        indexed_files.add(path)
        except Exception as e:
            print(f"⚠️ Query failed: {e}")

        coverage = {}
        for f in files:
            coverage[f] = f in indexed_files

        return coverage

    def scan(self):
        print("🗺️  Scanning Fog of War Coverage...")
        files = self.get_tracked_files()
        if not files:
            print("❌ No tracked files found (is this a git repo?).")
            return

        coverage_map = self.check_synapse_coverage(files)

        total_files = len(files)
        covered_files = sum(1 for v in coverage_map.values() if v)
        coverage_pct = (covered_files / total_files) * 100 if total_files > 0 else 0

        # Calculate Costs
        unindexed_tokens = 0
        unindexed_files = []

        for f, is_covered in coverage_map.items():
            if not is_covered:
                try:
                    size = os.path.getsize(f)
                    tokens = size / 4.0 # Crude approx
                    unindexed_tokens += tokens
                    unindexed_files.append(f)
                except OSError: pass

        print(f"\n📊 Coverage Report:")
        print(f"   - Tracked Files: {total_files}")
        print(f"   - Indexed in Synapse: {covered_files}")
        print(f"   - Coverage: {coverage_pct:.1f}%")
        print(f"   - Unindexed Files: {len(unindexed_files)}")
        print(f"   - Est. Exploration Cost: {int(unindexed_tokens)} Tokens")

        # Breakdown by Directory (Top Level)
        print("\n📁 Directory Breakdown (Unindexed):")
        dirs = {}
        for f in unindexed_files:
            d = f.split("/")[0] if "/" in f else "."
            dirs[d] = dirs.get(d, 0) + 1

        for d, count in sorted(dirs.items(), key=lambda x: x[1], reverse=True)[:5]:
             print(f"   - {d}/: {count} files")

        return {
            "coverage_pct": coverage_pct,
            "cost_estimate": int(unindexed_tokens),
            "unindexed_files": unindexed_files
        }

if __name__ == "__main__":
    mapper = FogCartographer()
    mapper.scan()
