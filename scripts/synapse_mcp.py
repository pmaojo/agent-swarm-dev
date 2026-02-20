#!/usr/bin/env python3
"""
Synapse MCP Server - Para Agent Swarm Development
Usa el SDK de Python de Synapse
"""

import sys
import json
from synapse import get_client

def handle_tool(tool_name: str, arguments: dict) -> str:
    """Maneja las llamadas de herramientas MCP"""
    client = get_client()
    namespace = arguments.get("namespace", "swarm")
    
    if tool_name == "query_graph":
        results = client.get_all_triples(namespace=namespace)
        return json.dumps(results, indent=2)
    
    elif tool_name == "ingest_triple":
        triple = {
            "subject": arguments.get("subject"),
            "predicate": arguments.get("predicate"),
            "object": arguments.get("object")
        }
        client.ingest_triples([triple], namespace=namespace)
        return f"✅ Added: {triple}"
    
    elif tool_name == "query_sparql":
        query = arguments.get("query", "")
        results = client.query_sparql(query, namespace=namespace)
        return json.dumps(results, indent=2)
    
    elif tool_name == "add_observation":
        triple = {
            "subject": arguments.get("subject"),
            "predicate": arguments.get("predicate"),
            "object": arguments.get("object")
        }
        client.ingest_triples([triple], namespace=namespace)
        return f"✅ Observation added: {triple}"
    
    elif tool_name == "ingest_memory":
        triples = arguments.get("triples", [])
        client.ingest_triples(triples, namespace=namespace)
        return f"✅ Ingested {len(triples)} triples"
    
    return f"❌ Unknown tool: {tool_name}"

def main():
    """MCP stdio server loop"""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line)
            
            # Handle MCP messages
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": "query_graph",
                                "description": "Query all triples in a namespace",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "namespace": {"type": "string", "default": "swarm"}
                                    }
                                }
                            },
                            {
                                "name": "ingest_triple",
                                "description": "Add a triple to the knowledge graph",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "subject": {"type": "string"},
                                        "predicate": {"type": "string"},
                                        "object": {"type": "string"},
                                        "namespace": {"type": "string", "default": "swarm"}
                                    },
                                    "required": ["subject", "predicate", "object"]
                                }
                            },
                            {
                                "name": "query_sparql",
                                "description": "Execute SPARQL query",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"},
                                        "namespace": {"type": "string", "default": "swarm"}
                                    },
                                    "required": ["query"]
                                }
                            },
                            {
                                "name": "add_observation",
                                "description": "Add observation to swarm memory",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "subject": {"type": "string"},
                                        "predicate": {"type": "string"},
                                        "object": {"type": "string"},
                                        "namespace": {"type": "string", "default": "swarm"}
                                    },
                                    "required": ["subject", "predicate", "object"]
                                }
                            },
                            {
                                "name": "ingest_memory",
                                "description": "Ingest multiple triples at once",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "triples": {"type": "array"},
                                        "namespace": {"type": "string", "default": "swarm"}
                                    },
                                    "required": ["triples"]
                                }
                            }
                        ]
                    }
                }
                print(json.dumps(response), flush=True)
            
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = handle_tool(tool_name, arguments)
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result
                            }
                        ]
                    }
                }
                print(json.dumps(response), flush=True)
            
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    main()
