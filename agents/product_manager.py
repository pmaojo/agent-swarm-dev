#!/usr/bin/env python3
"""
Product Manager Agent - Generates OpenSpec Requirements from user ideas.
Real implementation: Uses Trello Bridge and LLM.
"""
import os
import json
import sys
import time

# Add path to lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from llm import LLMService
from trello_bridge import TrelloBridge

# Add Synapse connectivity (reusing Coder's pattern or similar)
try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        from proto import semantic_engine_pb2, semantic_engine_pb2_grpc
import grpc

SWARM = "http://swarm.os/ontology/"

class ProductManagerAgent:
    def __init__(self):
        self.llm = LLMService()
        self.bridge = TrelloBridge() # Connects to Trello

        # Synapse Connection
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"⚠️ [Product Manager] Failed to connect to Synapse: {e}")

    def ingest_spec_triple(self, card_id: str, file_path: str):
        """Link Trello Card to OpenSpec File in Synapse."""
        if not self.stub: return

        # <CardID> <hasSpec> <FilePath>
        subject = f"{SWARM}trello/card/{card_id}"
        triples = [
            {"subject": subject, "predicate": f"{SWARM}hasOpenSpec", "object": f'"{file_path}"'},
            {"subject": subject, "predicate": f"{SWARM}type", "object": f"{SWARM}FeatureRequest"}
        ]

        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        try:
            self.stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace="default"))
            print(f"🔗 [Product Manager] Ingested spec link for card {card_id}")
        except Exception as e:
            print(f"⚠️ [Product Manager] Synapse ingestion failed: {e}")

    def generate_openspec(self, idea_description: str) -> str:
        """
        Takes a raw idea and converts it into a structured OpenSpec Markdown document.
        """
        print(f"📝 [Product Manager] Analyzing idea: {idea_description[:50]}...")

        system_prompt = """
        You are an expert Product Manager using the OpenSpec framework.
        Your goal is to transform a vague feature request into a structured Requirement Specification.

        Output Format:
        Use strictly the following Markdown structure:

        # [Feature Name] Specification

        ## Purpose
        [A concise summary of why this feature exists and what problem it solves.]

        ## Requirements
        [List of requirements using RFC 2119 keywords: SHALL, MUST, SHOULD.]
        - The system SHALL ...
        - The user MUST be able to ...

        ## Scenarios
        [Gherkin-style acceptance criteria]
        ### Scenario: [Name]
        - GIVEN [context]
        - WHEN [action]
        - THEN [outcome]

        Do not include any other text or conversational filler. Just the Markdown content.
        """

        try:
            response = self.llm.get_completion(f"Feature Request: {idea_description}", system_prompt)
            return response
        except Exception as e:
            print(f"❌ [Product Manager] LLM Generation Failed: {e}")
            return ""

    def save_spec_file(self, feature_name: str, content: str):
        """Saves the spec to openspec/specs/<feature>/spec.md"""
        # Sanitize feature name for folder path
        safe_name = "".join([c if c.isalnum() else "-" for c in feature_name.lower()])
        path = f"openspec/specs/{safe_name}/spec.md"

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

        print(f"💾 [Product Manager] Saved spec to {path}")
        return path

    def process_card(self, card: dict):
        """
        Main logic: INBOX -> REQUIREMENTS
        1. Read card.
        2. Generate OpenSpec.
        3. Save file.
        4. Update Trello (Description + Move).
        5. Ingest Triples.
        """
        card_id = card['id']
        name = card['name']
        desc = card['desc'] or name # Use name if desc is empty

        print(f"🚀 [Product Manager] Processing card '{name}'...")

        # Generate Spec
        spec_content = self.generate_openspec(desc)
        if not spec_content:
            print("❌ Failed to generate spec.")
            return

        # Save to Repo
        file_path = self.save_spec_file(name, spec_content)

        # Update Trello Description
        self.bridge.update_card_desc(card_id, spec_content)
        self.bridge.add_comment(card_id, f"✅ **OpenSpec Generated!**\n\nFile: `{file_path}`")

        # Ingest to Synapse
        self.ingest_spec_triple(card_id, file_path)

        # Move to REQUIREMENTS
        self.bridge.move_card(card_id, "REQUIREMENTS")

    def run(self):
        """Start the agent in listening mode."""
        print("👀 Product Manager Agent watching [INBOX]...")
        # Register callback for INBOX list
        self.bridge.register_callback("INBOX", self.process_card)
        self.bridge.sync_loop()

if __name__ == "__main__":
    agent = ProductManagerAgent()
    agent.run()
