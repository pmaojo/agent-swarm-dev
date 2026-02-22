import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

class FogService:
    def __init__(self, orchestrator):
        self.orch = orchestrator

    def get_fog_state(self) -> Dict[str, str]:
        """
        Returns a map of {node_id: "visible" | "fogged"}.
        Logic: Nodes associated with active agents or recent events are "visible".
        Everything else is "fogged" until an Analyst explores it.
        """
        if not self.orch.stub:
            return {}

        # 1. Get Active Agents' Locations (Tasks/Artifacts)
        # Query: Find all subjects/objects associated with an Agent via `prov:wasAssociatedWith`
        # within the last 24 hours.
        yesterday = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

        # Simplified query for MVP: Get all triples linked to Agents
        query = f"""
        PREFIX swarm: <http://swarm.os/ontology/>
        PREFIX prov: <http://www.w3.org/ns/prov#>

        SELECT DISTINCT ?s ?o
        WHERE {{
            ?s prov:wasAssociatedWith ?agent .
            OPTIONAL {{ ?s ?p ?o }}
        }}
        LIMIT 100
        """

        visible_nodes = set()
        try:
            results = self.orch.query_graph(query)
            for row in results:
                s = row.get("?s") or row.get("s")
                o = row.get("?o") or row.get("o")
                if s: visible_nodes.add(str(s))
                if o: visible_nodes.add(str(o))
        except Exception as e:
            print(f"Error fetching fog state: {e}")

        # 2. Get All Nodes (to mark others as fogged)
        # For MVP, we just return the visible ones and let client default others to fog.
        # But user asked for "areas... appear darkened".
        # Let's return a "visibility_map".

        fog_map = {}
        for node in visible_nodes:
            # Clean URI
            node_id = node.strip('<>"')
            fog_map[node_id] = "visible"

        return fog_map

    def get_analyst_vision(self) -> List[str]:
        """Specific logic for Analyst: Returns nodes they have 'scanned'."""
        # Query for Analyst specific interactions
        # ...
        return []
