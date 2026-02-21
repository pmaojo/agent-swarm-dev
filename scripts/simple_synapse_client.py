import json
import subprocess
import os

class SynapseClient:
    def __init__(self):
        self.binary = "./synapse"

    def _run_mcp(self, request_data):
        """Run synapse in MCP mode for a single request"""
        env = os.environ.copy()
        env["EMBEDDING_PROVIDER"] = "remote"
        env["EMBEDDING_API_URL"] = "http://localhost:11434/api/embeddings"

        try:
            process = subprocess.Popen(
                [self.binary, "--mcp"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )

            # MCP JSON-RPC Request
            json_req = json.dumps(request_data) + "\n"
            stdout, stderr = process.communicate(input=json_req, timeout=15)

            # Parse line-by-line JSON-RPC output
            for line in stdout.splitlines():
                if not line.strip(): continue
                try:
                    resp = json.loads(line)
                    if resp.get("id") == request_data.get("id"):
                        if "error" in resp:
                            return {"error": resp["error"]}
                        # Success result
                        result = resp.get("result", {})
                        content = result.get("content", [])
                        if content and content[0]["type"] == "text":
                            # The tool result is often a JSON string inside 'text'
                            try:
                                return json.loads(content[0]["text"])
                            except:
                                return content[0]["text"]
                        return result
                except:
                    continue

            return {"error": "No valid response", "stderr": stderr}

        except Exception as e:
            return {"error": str(e)}

    def ingest_triples(self, triples, namespace="default"):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "ingest_triples",
                "arguments": {"triples": triples, "namespace": namespace}
            }
        }
        return self._run_mcp(req)

    def sparql_query(self, query, namespace="default"):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "sparql_query",
                "arguments": {"query": query, "namespace": namespace}
            }
        }
        return self._run_mcp(req)

    def hybrid_search(self, query, namespace="default", limit=5):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "hybrid_search",
                "arguments": {"query": query, "namespace": namespace, "limit": limit} # Note: check if tool uses 'limit' or 'k'
            }
        }
        return self._run_mcp(req)

def get_client():
    return SynapseClient()
