"""
Synapse Client - Direct connection to Synapse gRPC/HTTP/MCP
For this environment, we communicate with the running 'synapse' process via its Stdio/MCP interface or HTTP.
Since we are in a dev environment and 'synapse' is running, we can implement a simple client that
talks to the MCP stdio interface or just re-implements the logic if needed.

However, the cleanest way given the context is to use a direct gRPC client if available,
or just wrap the MCP stdio communication with the local binary.
"""

import sys
import json
import subprocess
import os
from typing import List, Dict, Any, Optional

class SynapseClient:
    def __init__(self, binary_path="./synapse"):
        self.binary_path = binary_path
        self.env = os.environ.copy()
        # Ensure we point to remote embeddings
        self.env["EMBEDDING_PROVIDER"] = "remote"
        self.env["EMBEDDING_API_URL"] = "http://localhost:11434/api/embeddings"

    def _call_mcp(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        Calls the Synapse binary in MCP mode for a single request.
        Note: The binary typically runs as a server. For CLI-like one-off usage,
        we might need a different approach or use the server if running.

        If the server is already running, we should connect to it.
        But Synapse v0.8.5 via `synapse` binary usually runs a gRPC server by default,
        or MCP loop if `--mcp` passed.

        If we want to use the running server, we need a gRPC client.
        If we want to use the binary directly (CLI style), we can run it.

        Wait, the previous SDK implementation was calling `mcporter`.
        We don't have `mcporter`.

        Let's try to communicate with the running server via gRPC if possible,
        or just spawn the binary for each command if it supports CLI args.
        Checking `synapse --help` would be useful but we can't see output easily.

        Alternative: The `synapse-sdk` we saw earlier seemed to rely on `mcporter` which is an MCP client.

        Let's implement a simple wrapper that runs `synapse --mcp` and sends one JSON-RPC message to stdin.
        """

        # Prepare JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": f"tools/call",
            "params": {
                "name": tool_name,
                "arguments": args
            }
        }

        try:
            # Run synapse in MCP mode for one-shot
            process = subprocess.Popen(
                [self.binary_path, "--mcp"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                text=True
            )

            json_input = json.dumps(request) + "\n"
            stdout, stderr = process.communicate(input=json_input, timeout=30)

            if process.returncode != 0:
                print(f"Synapse Error (stderr): {stderr}")
                return {"error": stderr}

            # Parse output - look for JSON-RPC response
            # MCP output might be line-delimited
            for line in stdout.splitlines():
                try:
                    data = json.loads(line)
                    if data.get("id") == 1 and "result" in data:
                        # Extract the tool result
                        content = data["result"].get("content", [])
                        if content and content[0].get("type") == "text":
                            # The tool usually returns a JSON string inside the text field
                            text_res = content[0]["text"]
                            try:
                                return json.loads(text_res)
                            except:
                                return text_res
                        return data["result"]
                    if "error" in data:
                        return {"error": data["error"]}
                except:
                    continue

            return {"error": "No valid JSON-RPC response found", "raw": stdout}

        except Exception as e:
            return {"error": str(e)}

    def ingest_triples(self, triples: List[Dict], namespace="default"):
        return self._call_mcp("ingest_triples", {"triples": triples, "namespace": namespace})

    def sparql_query(self, query: str, namespace="default"):
        return self._call_mcp("sparql_query", {"query": query, "namespace": namespace})

    def hybrid_search(self, query: str, namespace="default", limit=10):
        # Note: tool might expect different args, e.g. 'k' or 'limit'
        return self._call_mcp("hybrid_search", {"query": query, "namespace": namespace, "limit": limit})

def get_client():
    return SynapseClient()
