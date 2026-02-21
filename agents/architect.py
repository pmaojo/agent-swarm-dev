#!/usr/bin/env python3
"""
Architect Agent - Designs technical implementation from OpenSpec.
Real implementation: Uses Trello Bridge, File System Ground Truth, and LLM.
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

# Add Synapse connectivity
try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        from proto import semantic_engine_pb2, semantic_engine_pb2_grpc
import grpc

SWARM = "http://swarm.os/ontology/"

class ArchitectAgent:
    def __init__(self):
        self.llm = LLMService()
        self.bridge = TrelloBridge()

        # Synapse Connection
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            grpc.channel_ready_future(self.channel).result(timeout=5)
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"⚠️ [Architect] Failed to connect to Synapse: {e}")

    def ingest_design_triple(self, card_id: str, file_path: str):
        """Link Trello Card to Design File in Synapse."""
        if not self.stub: return

        # <CardID> <hasDesign> <FilePath>
        subject = f"{SWARM}trello/card/{card_id}"
        triples = [
            {"subject": subject, "predicate": f"{SWARM}hasTechnicalDesign", "object": f'"{file_path}"'},
            {"subject": subject, "predicate": f"{SWARM}status", "object": '"DESIGNED"'}
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
            print(f"🔗 [Architect] Ingested design link for card {card_id}")
        except Exception as e:
            print(f"⚠️ [Architect] Synapse ingestion failed: {e}")

    def generate_design(self, spec_content: str) -> str:
        """
        Takes an OpenSpec and generates a Technical Design (OpenSpec Change Proposal).
        """
        print(f"📐 [Architect] Designing solution based on spec...")

        system_prompt = """
        You are a Senior System Architect using the OpenSpec framework.
        Your goal is to create a technical design document based on the provided Requirement Specification.

        Output Format:
        Use strictly the following Markdown structure:

        # Technical Design: [Feature Name]

        ## Architecture
        [Describe the high-level architecture: components, data flow, external services.]
        - Component A -> Component B
        - Database Schema: ...

        ## Implementation Plan
        [Step-by-step plan for the developer.]
        1. Create new service `service_name`.
        2. Implement API endpoint `/api/v1/resource`.
        3. Add unit tests.

        ## Tasks (Checklist)
        [Detailed tasks for Trello checklist]
        - [ ] Task 1
        - [ ] Task 2
        - [ ] Task 3

        Do not include any other text.
        """

        try:
            response = self.llm.get_completion(f"Requirement Specification:\n{spec_content}", system_prompt)
            return response
        except Exception as e:
            print(f"❌ [Architect] LLM Generation Failed: {e}")
            return ""

    def save_design_file(self, feature_name: str, content: str):
        """Saves the design to openspec/changes/<feature>/design.md"""
        safe_name = "".join([c if c.isalnum() else "-" for c in feature_name.lower()])
        path = f"openspec/changes/{safe_name}/design.md"

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

        print(f"💾 [Architect] Saved design to {path}")
        return path

    def get_spec_from_repo(self, feature_name: str) -> str:
        """Attempts to read the spec from the file system based on feature name."""
        safe_name = "".join([c if c.isalnum() else "-" for c in feature_name.lower()])
        path = f"openspec/specs/{safe_name}/spec.md"

        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read()
        return ""

    def process_card(self, card: dict):
        """
        Main logic: REQUIREMENTS -> DESIGN
        1. Read spec from REPO (Ground Truth). Fallback to Trello Desc.
        2. Generate Design.
        3. Save file.
        4. Update Trello (Comment + Move).
        5. Ingest Triples.
        """
        card_id = card['id']
        name = card['name']
        desc = card['desc']

        print(f"🚀 [Architect] Processing card '{name}'...")

        # 1. Ground Truth Check
        spec_content = self.get_spec_from_repo(name)
        if spec_content:
            print(f"✅ Found Spec in Repo for '{name}'")
        else:
            print(f"⚠️ Spec file missing for '{name}'. Using Trello description as fallback.")
            spec_content = desc

        if not spec_content or len(spec_content) < 10:
            print("⚠️ Spec content empty/too short. Proceeding with raw idea name.")
            spec_content = name

        # 2. Generate Design
        design_content = self.generate_design(spec_content)
        if not design_content:
            print("❌ Failed to generate design.")
            return

        # 3. Save to Repo
        file_path = self.save_design_file(name, design_content)

        # 4. Update Trello
        comment = f"📐 **Technical Design Ready!**\n\nFile: `{file_path}`\n\n---\n\n{design_content}"
        self.bridge.add_comment(card_id, comment)
        # Also update desc to include link to design? Or just comment is enough.
        # Let's keep desc as Spec (The "What") and comments/linked file as Design (The "How").

        # 5. Ingest to Synapse
        self.ingest_design_triple(card_id, file_path)

        # 6. Move to DESIGN (Wait for Approval)
        self.bridge.move_card(card_id, "DESIGN")

    def run(self):
        """Start the agent in listening mode."""
        print("👀 Architect Agent watching [REQUIREMENTS]...")
        self.bridge.register_callback("REQUIREMENTS", self.process_card)
        self.bridge.sync_loop()

if __name__ == "__main__":
    agent = ArchitectAgent()
    agent.run()
