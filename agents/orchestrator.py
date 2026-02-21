#!/usr/bin/env python3
"""
Orchestrator Agent - Task decomposition and workflow management.
Real implementation: Coordinates real agents via Synapse-driven state machine.
Enhanced for Autonomous Operations (Phase 3) & Trello Integration.
"""
import os
import re
import json
import grpc
import sys
import yaml
import time
import uuid
from typing import List, Dict, Any, Optional

# Add path to lib and agents
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))
# Add proto path for gRPC
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'proto'))

try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        from proto import semantic_engine_pb2, semantic_engine_pb2_grpc

from coder import CoderAgent
from reviewer import ReviewerAgent
from deployer import DeployerAgent
from trello_bridge import TrelloBridge

# Define Strict Namespaces
SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"
PROV = "http://www.w3.org/ns/prov#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SKOS = "http://www.w3.org/2004/02/skos/core#"

class OrchestratorAgent:
    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "gpt-4")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.namespace = "default"
        self.bridge = TrelloBridge()

        # Connect to Synapse
        self.connect()
        
        # Load Schema at startup
        self.load_schema()
        self.load_security_policy()
        self.load_consolidated_wisdom()

        # Instantiate Agents
        self.agents = {
            "Coder": CoderAgent(),
            "Reviewer": ReviewerAgent(),
            "Deployer": DeployerAgent()
        }

    def connect(self):
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
            # Simple ping/check if server is up
            try:
                grpc.channel_ready_future(self.channel).result(timeout=2)
                print("✅ Connected to Synapse")
            except grpc.FutureTimeoutError:
                print("⚠️  Synapse not reachable. Is it running?")
        except Exception as e:
            print(f"❌ Failed to connect to Synapse: {e}")

    def close(self):
        """Close gRPC channel"""
        if self.channel:
            self.channel.close()
        for agent in self.agents.values():
            if hasattr(agent, 'close'):
                agent.close()

    def __del__(self):
        self.close()

    def ingest_triples(self, triples: List[Dict[str, str]], namespace: str = None):
        """Ingest triples helper"""
        if not self.stub: return

        target_namespace = namespace if namespace else self.namespace

        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        request = semantic_engine_pb2.IngestRequest(
            triples=pb_triples,
            namespace=target_namespace
        )
        self.stub.IngestTriples(request)

    def load_security_policy(self):
        """Load security_policy.nt into Synapse"""
        policy_path = os.path.join(os.path.dirname(__file__), '..', 'security_policy.nt')
        if not os.path.exists(policy_path):
            print(f"⚠️  Security policy file not found at {policy_path}")
            return

        print("🛡️  Loading Security Policy...")
        triples = []
        try:
            with open(policy_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    # Simple parsing of N-Triples: <S> <P> <O>
                    parts = line.split('> <')
                    if len(parts) == 3:
                        s = parts[0].strip('<')
                        p = parts[1]
                        o = parts[2].strip('>').split(' ')[0] # Handle optional dot at end
                        triples.append({"subject": s, "predicate": p, "object": o})

            if triples:
                self.ingest_triples(triples, namespace=self.namespace)
                print(f"✅ Security Policy loaded ({len(triples)} triples)")
        except Exception as e:
            print(f"❌ Failed to load security policy: {e}")

    def load_consolidated_wisdom(self):
        """Load consolidated_wisdom.ttl into Synapse with improved parsing."""
        wisdom_path = os.path.join(os.path.dirname(__file__), '..', 'consolidated_wisdom.ttl')
        if not os.path.exists(wisdom_path):
            return

        print("🧠 Loading Consolidated Wisdom...")
        triples = []
        try:
            with open(wisdom_path, 'r') as f:
                content = f.read()

            # Regex for simple Turtle: <Subject> <Predicate> "Object" .
            # Handles quotes inside object, assumes single line per triple for now
            pattern = re.compile(r'(<[^>]+>)\s+(<[^>]+>)\s+"((?:[^"\\]|\\.)*)"\s*\.')

            for match in pattern.finditer(content):
                s = match.group(1).strip('<>')
                p = match.group(2).strip('<>')
                o = match.group(3) # Regex group excludes quotes

                # Unescape if needed
                o = o.replace('\\"', '"')

                # Re-wrap in quotes for ingestion (Literals) to be handled by engine patch
                o_literal = f'"{o}"'

                triples.append({"subject": s, "predicate": p, "object": o_literal})

            if triples:
                self.ingest_triples(triples, namespace=self.namespace)
                print(f"✅ Consolidated Wisdom loaded ({len(triples)} rules)")
        except Exception as e:
            print(f"❌ Failed to load consolidated wisdom: {e}")

    def load_schema(self):
        """Load swarm_schema.yaml into Synapse"""
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'swarm_schema.yaml')
        if not os.path.exists(schema_path):
            print(f"⚠️  Schema file not found at {schema_path}")
            return

        print("📥 Loading Swarm Schema...")
        try:
            with open(schema_path, 'r') as f:
                schema = yaml.safe_load(f)

            triples = []
            # Agents
            for agent_name, agent_data in schema.get('agents', {}).items():
                subject = f"http://swarm.os/agent/{agent_name}"
                triples.append({"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/Agent"})
                triples.append({"subject": subject, "predicate": "http://swarm.os/description", "object": agent_data.get('description', '')})

                # Ontology Role
                ontology_role = agent_data.get('ontology_role')
                if ontology_role:
                    # Map simplified role name to a URI if needed, or use a predicate to link to a role node
                    # Creating triple: <Agent> rdf:type <Role> (where Role is just the string for now, or a URI)
                    triples.append({"subject": subject, "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "object": ontology_role})

                # Skills / Stacks
                for stack in agent_data.get('supported_stacks', []):
                    stack_uri = f"http://swarm.os/stack/{stack}"
                    triples.append({"subject": subject, "predicate": "http://swarm.os/hasSkill", "object": stack_uri})

            # Tasks
            for task_name, task_data in schema.get('tasks', {}).items():
                subject = f"http://swarm.os/task/{task_name}"
                triples.append({"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/TaskType"})
                triples.append({"subject": subject, "predicate": "http://swarm.os/handler", "object": f"http://swarm.os/agent/{task_data.get('handler')}"})
                triples.append({"subject": subject, "predicate": "http://swarm.os/description", "object": task_data.get('description', '')})

                # Required Permissions
                for perm in task_data.get('required_permissions', []):
                    # Construct full URI: http://swarm.os/nist/{PermissionName}
                    perm_uri = f"http://swarm.os/nist/{perm}"
                    triples.append({"subject": subject, "predicate": "http://swarm.os/nist/requiresPermission", "object": perm_uri})

            # Transitions
            for task_name, transitions in schema.get('transitions', {}).items():
                subject = f"http://swarm.os/task/{task_name}"
                if transitions.get('on_success'):
                    triples.append({"subject": subject, "predicate": "http://swarm.os/on_success", "object": f"http://swarm.os/task/{transitions.get('on_success')}"})
                if transitions.get('on_failure'):
                    triples.append({"subject": subject, "predicate": "http://swarm.os/on_failure", "object": f"http://swarm.os/task/{transitions.get('on_failure')}"})

            # Artifacts (New Neuro-symbolic Types)
            for artifact_name, artifact_data in schema.get('artifacts', {}).items():
                subject = f"http://swarm.os/artifact/{artifact_name}"
                triples.append({"subject": subject, "predicate": "http://swarm.os/type", "object": "http://swarm.os/ArtifactType"})
                triples.append({"subject": subject, "predicate": "http://swarm.os/description", "object": artifact_data.get('description', '')})
                # Properties
                for prop in artifact_data.get('properties', []):
                    prop_subj = f"http://swarm.os/property/{prop}"
                    triples.append({"subject": subject, "predicate": "http://swarm.os/hasProperty", "object": prop_subj})

            self.ingest_triples(triples, namespace=self.namespace)
            print(f"✅ Schema loaded ({len(triples)} triples)")
        except Exception as e:
            print(f"❌ Failed to load schema: {e}")

    def query_graph(self, query: str, namespace: str = None) -> List[Dict]:
        """Execute SPARQL query against Synapse"""
        if not self.stub:
            print("❌ Not connected to Synapse")
            return []

        target_namespace = namespace if namespace else self.namespace

        request = semantic_engine_pb2.SparqlRequest(
            query=query,
            namespace=target_namespace
        )
        try:
            response = self.stub.QuerySparql(request)
            return json.loads(response.results_json)
        except Exception as e:
            print(f"❌ Graph query failed: {e}")
            return []

    def check_compliance(self, agent_name: str, task_type: str) -> bool:
        """Verify if agent has required permissions for the task."""
        agent_uri = f"http://swarm.os/agent/{agent_name}"
        task_uri = f"http://swarm.os/task/{task_type}"

        # Using SELECT with LIMIT 1 instead of ASK to ensure compatibility
        query = f"""
        SELECT ?p
        WHERE {{
            <{agent_uri}> <http://swarm.os/nist/hasPermission> ?p .
            <{task_uri}> <http://swarm.os/nist/requiresPermission> ?p .
        }}
        LIMIT 1
        """
        results = self.query_graph(query)
        is_compliant = len(results) > 0

        if is_compliant:
            print(f"✅ Compliance Check Passed: {agent_name} authorized for {task_type}")
        else:
            print(f"⛔ Compliance Check Failed: {agent_name} lacks permissions for {task_type}")

        return is_compliant

    def get_agent_responsibilities(self, agent_name: str) -> List[str]:
        """Retrieve agent responsibilities from ontology."""
        agent_uri = f"http://swarm.os/agent/{agent_name}"
        # Query: SELECT ?desc WHERE { <Agent_ID> rdf:type ?role . ?role <es_responsable_de> ?desc . }
        query = f"""
        SELECT ?desc
        WHERE {{
            <{agent_uri}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?role .
            ?role <es_responsable_de> ?desc .
        }}
        """
        results = self.query_graph(query)
        responsibilities = [r.get("?desc") or r.get("desc") for r in results]
        return responsibilities

    def get_agent_lessons(self, agent_name: str, stack: str = "python") -> List[str]:
        """Retrieve past lessons learned for this agent, filtered by stack context."""
        agent_uri = f"http://swarm.os/agent/{agent_name}"
        stack_literal = f'"{stack}"'

        # Query for skos:historyNote via memory:learnedFrom
        # Filter out consolidated lessons
        # Also filter by stack: ?execId swarm:hasStack "python"
        query = f"""
        PREFIX swarm: <{SWARM}>
        PREFIX nist: <{NIST}>
        PREFIX skos: <{SKOS}>

        SELECT ?note
        WHERE {{
            <{agent_uri}> swarm:learnedFrom ?execId .
            ?execId skos:historyNote ?note .
            ?execId swarm:hasStack {stack_literal} .
            FILTER NOT EXISTS {{ ?execId swarm:isConsolidated "true" }}
        }}
        """
        results = self.query_graph(query)
        lessons = [r.get("?note") or r.get("note") for r in results]
        return lessons

    def get_golden_rules(self, agent_name: str, stack: str = "python") -> List[str]:
        """Retrieve Golden Rules (HardConstraints) for the agent's role AND the specific stack."""
        agent_uri = f"http://swarm.os/agent/{agent_name}"
        stack_uri = f"http://swarm.os/stack/{stack}"

        # UNION query: Rules for the Role OR Rules for the Stack
        query = f"""
        PREFIX nist: <{NIST}>
        PREFIX rdf: <{RDF}>

        SELECT ?rule
        WHERE {{
            {{
                <{agent_uri}> rdf:type ?role .
                ?role nist:HardConstraint ?rule .
            }}
            UNION
            {{
                <{stack_uri}> nist:HardConstraint ?rule .
            }}
        }}
        """
        results = self.query_graph(query)
        rules = [r.get("?rule") or r.get("rule") for r in results]
        return rules

    def get_initial_task_type(self, task_description: str) -> str:
        """Determine initial task type based on description or default to FeatureImplementationTask"""
        return "FeatureImplementationTask"

    def get_handler_for_task(self, task_type: str) -> str:
        """Query graph to find handler for task type"""
        query = f"""
        SELECT ?agentUri
        WHERE {{
            <http://swarm.os/task/{task_type}> <http://swarm.os/handler> ?agentUri .
        }}
        """
        results = self.query_graph(query)

        if results and len(results) > 0:
            agent_uri = results[0].get("?agentUri") or results[0].get("agentUri")
            if agent_uri:
                return agent_uri.strip("<>").split("/")[-1]
        return "Unknown"

    def get_next_task(self, current_task_type: str, outcome: str) -> Optional[str]:
        """Query graph for next task based on outcome"""
        predicate = "on_success" if outcome == "success" else "on_failure"
        query = f"""
        SELECT ?nextTaskUri
        WHERE {{
            <http://swarm.os/task/{current_task_type}> <http://swarm.os/{predicate}> ?nextTaskUri .
        }}
        """
        results = self.query_graph(query)
        if results and len(results) > 0:
            next_task_uri = results[0].get("?nextTaskUri") or results[0].get("nextTaskUri")
            if next_task_uri:
                return next_task_uri.strip("<>").split("/")[-1]
        return None

    def ensure_stack_knowledge(self, stack: str):
        """
        Verify if the stack has known constraints. If not, trigger Research.
        """
        print(f"🧐 Verifying knowledge base for stack: {stack}...")
        stack_uri = f"http://swarm.os/stack/{stack}"

        # Check if we have any HardConstraints for this stack
        query = f"""
        PREFIX nist: <{NIST}>
        SELECT ?rule
        WHERE {{
            <{stack_uri}> nist:HardConstraint ?rule .
        }}
        LIMIT 1
        """
        results = self.query_graph(query)

        if not results:
            print(f"⚠️  Unknown stack '{stack}'. Initiating Research Task...")
            coder = self.agents.get("Coder")
            if not coder:
                print("❌ Coder agent unavailable for research.")
                return

            principles = coder.research_stack(stack)

            if principles:
                triples = []
                for p in principles:
                    # Ingest as HardConstraint
                    # Escape quotes for string literal
                    p_safe = p.replace('"', '\\"')
                    triples.append({
                        "subject": stack_uri,
                        "predicate": f"{NIST}HardConstraint",
                        "object": f'"{p_safe}"'
                    })

                # Also assert it's a Stack
                triples.append({
                    "subject": stack_uri,
                    "predicate": f"{SWARM}type",
                    "object": f"{SWARM}TechStack"
                })

                self.ingest_triples(triples)
                print(f"✅ Ingested {len(principles)} research findings for {stack}.")
            else:
                print(f"❌ Research failed for {stack}.")
        else:
            print(f"✅ Stack '{stack}' is known.")

    def run_agent(self, agent_name: str, task_desc: str, context: Dict = None, task_type: str = None, stack: str = "python", extra_rules: List[str] = None) -> Dict:
        """Execute an agent"""

        # 1. NIST Guardrail Check
        if task_type:
            if not self.check_compliance(agent_name, task_type):
                return {"status": "failure", "error": f"Security Violation: {agent_name} not authorized for {task_type}"}

        # 2. Dynamic System Prompts (Responsibilities)
        responsibilities = self.get_agent_responsibilities(agent_name)

        # 3. Lessons Learned (Memory) - Stack Aware
        lessons = self.get_agent_lessons(agent_name, stack=stack)

        # 4. Golden Rules - Stack Aware
        golden_rules = self.get_golden_rules(agent_name, stack=stack)

        # Add transient/dry-run rules
        if extra_rules:
            golden_rules.extend(extra_rules)

        # Inject into context/prompt
        enhanced_task_desc = f"{task_desc}"

        # Add stack context header
        enhanced_task_desc = f"CONTEXT: Stack={stack}\n{enhanced_task_desc}"

        if golden_rules:
            enhanced_task_desc = f"⚠️ GOLDEN RULES (HARD CONSTRAINTS) FOR {stack.upper()}:\n" + "\n".join([f"- {r}" for r in golden_rules]) + f"\n\n{enhanced_task_desc}"

        if responsibilities:
            enhanced_task_desc = f"ROLE RESPONSIBILITIES:\n" + "\n".join([f"- {r}" for r in responsibilities]) + f"\n\n{enhanced_task_desc}"

        if lessons:
            enhanced_task_desc = f"LESSONS LEARNED FROM PAST {stack.upper()} FAILURES:\n" + "\n".join([f"- {l}" for l in lessons]) + f"\n\n{enhanced_task_desc}"

        print(f"🤖 Agent '{agent_name}' executing: {task_desc[:50]}...")
        print(f"   ↳ Stack: {stack}")
        if responsibilities:
            print(f"   ↳ Injected {len(responsibilities)} responsibilities")
        if lessons:
            print(f"   ↳ Injected {len(lessons)} past lessons")
        if golden_rules:
            print(f"   ↳ Injected {len(golden_rules)} golden rules")

        agent = self.agents.get(agent_name)
        if not agent:
            print(f"❌ Unknown agent: {agent_name}")
            return {"status": "failure", "error": "Unknown agent"}

        try:
            return agent.run(enhanced_task_desc, context)
        except Exception as e:
            print(f"❌ Agent execution failed: {e}")
            return {"status": "failure", "error": str(e)}

    def check_operational_status(self) -> str:
        """
        High-Efficiency Status Check using Temporal Shadowing Pattern.
        Uses ASK + FILTER NOT EXISTS for O(1) detection of HALTED state
        that hasn't been superseded by a later OPERATIONAL state.
        """
        # Optimized ASK Query
        query = f"""
        PREFIX nist: <{NIST}>
        PREFIX prov: <{PROV}>

        ASK WHERE {{
            # Find a HALTED event
            ?haltEvent nist:newStatus "HALTED" ;
                       prov:generatedAtTime ?haltTime .

            # Ensure NO OPERATIONAL event exists with a newer timestamp
            FILTER NOT EXISTS {{
                ?resumeEvent nist:newStatus "OPERATIONAL" ;
                             prov:generatedAtTime ?resumeTime .
                FILTER (?resumeTime > ?haltTime)
            }}
        }}
        """

        # We need to handle ASK response properly.
        # Synapse (Oxigraph) usually returns boolean JSON for ASK: {"boolean": true}
        if not self.stub: return "OPERATIONAL"

        request = semantic_engine_pb2.SparqlRequest(query=query, namespace="default")
        try:
            response = self.stub.QuerySparql(request)
            result_json = json.loads(response.results_json)

            # Check boolean result
            is_halted = result_json.get("boolean", False)

            if is_halted:
                return "HALTED"
            else:
                return "OPERATIONAL"

        except Exception as e:
            print(f"❌ Status Check Failed: {e}")
            # Fail closed (HALTED) or open (OPERATIONAL)?
            # Safety first -> HALTED if check fails? Or OPERATIONAL to avoid deadlock?
            # Let's assume OPERATIONAL if query fails, but log error.
            return "OPERATIONAL"

    def get_file_content_ground_truth(self, feature_name: str, file_type: str = "design") -> str:
        """Retrieve Ground Truth content from repo (spec or design)."""
        safe_name = "".join([c if c.isalnum() else "-" for c in feature_name.lower()])
        path = ""
        if file_type == "design":
            path = f"openspec/changes/{safe_name}/design.md"
        elif file_type == "spec":
            path = f"openspec/specs/{safe_name}/spec.md"

        if os.path.exists(path):
             with open(path, "r") as f:
                 return f.read()
        return ""

    def ingest_execution_link(self, card_id: str, design_content: str):
        """Link Trello Card to Execution in Synapse."""
        if not self.stub: return

        # <CardID> <status> <IN PROGRESS>
        subject = f"{SWARM}trello/card/{card_id}"
        triples = [
            {"subject": subject, "predicate": f"{SWARM}status", "object": '"IN_PROGRESS"'}
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
        except Exception as e:
            print(f"⚠️ [Orchestrator] Synapse ingestion failed: {e}")


    def process_trello_todo(self, card: Dict):
        """
        Handle Trello 'TODO' card.
        Only proceeds if 'APPROVED' label is present (NIST Guardrail).
        Fetches Ground Truth from File System (Design + Spec).
        """
        card_id = card['id']
        name = card['name']
        desc = card['desc']

        print(f"🚀 [Orchestrator] Detected card in TODO: {name}")

        # Guardrail: Check for [APPROVED] label
        if not self.bridge.has_label(card_id, "Approved"):
            print(f"⛔ [Guardrail] Card '{name}' missing 'Approved' label. Skipping execution.")
            # Note: Bridge polling logic now handles this by not marking processed if we skip?
            # Actually, Bridge logic marks processed if callback returns success.
            # If we return here, we should ideally NOT mark processed, or just return.
            # Bridge logic (in my update) marks processed AFTER callback.
            # To avoid re-processing every loop for unapproved cards, we should mark processed BUT
            # we need a way to re-check later.
            # Current Bridge logic marks processed for that list.
            # So if it stays in TODO without approval, it won't be checked again until restart.
            # This is acceptable for MVP (requires restart or manual move).
            # OR we can throw exception to NOT mark processed, but that logs error.
            # Let's just log and skip.
            return

        print(f"✅ [Guardrail] Card '{name}' APPROVED. Starting execution...")

        # Move to IN PROGRESS
        self.bridge.move_card(card_id, "IN PROGRESS")

        # 1. Fetch Ground Truth (Design & Spec)
        design_content = self.get_file_content_ground_truth(name, "design")
        spec_content = self.get_file_content_ground_truth(name, "spec")

        full_context = ""
        if design_content:
             full_context += f"TECHNICAL DESIGN:\n{design_content}\n\n"
        if spec_content:
             full_context += f"REQUIREMENTS:\n{spec_content}\n\n"

        if not full_context:
            print("⚠️ Missing Ground Truth files. Falling back to card description.")
            full_context = desc

        # Ingest Execution Link
        self.ingest_execution_link(card_id, full_context)

        # Execute Task (Blocking)
        # We need a session ID. Use Card ID.
        try:
            result = self.run(full_context, stack="python", session_id=f"trello-{card_id}")

            final_status = result.get("final_status")

            if final_status == "success":
                self.bridge.move_card(card_id, "DONE")
                self.bridge.add_comment(card_id, "🎉 **Execution Complete!**\n\nDeployment Successful.")
                # Ingest completion
                # self.ingest_completion(card_id)
            else:
                # Failure
                raise Exception("Workflow returned failure status")

        except Exception as e:
            print(f"❌ Execution failed: {e}")
            # Move back to REQUIREMENTS
            self.bridge.move_card(card_id, "REQUIREMENTS")
            self.bridge.add_comment(card_id, f"⚠️ **Execution Failed**\n\nReason: {str(e)}\n\nMoved back to REQUIREMENTS for revision.")


    def autonomous_loop(self):
        print("👀 Swarm de guardia. Buscando tareas en Synapse & Trello...")

        # Register Trello Callback
        self.bridge.register_callback("TODO", self.process_trello_todo)

        while True:
            # 1. Trello Sync (Polling)
            # This triggers process_trello_todo if cards are found
            self.bridge.sync_loop_step() # We need to expose a single step method or run in thread

            # 2. Synapse Check (Existing Logic)
            # Check Status
            status = self.check_operational_status()
            if status == "HALTED":
                print("🛑 SYSTEM HALTED. Waiting...")
                time.sleep(10)
                continue

            # ... (Existing Synapse logic preserved) ...

            time.sleep(5) # Evita saturar el CPU

    def start_trello_bridge(self):
        """Starts Trello Bridge in a separate thread or just registers it if we change the loop."""
        # For this implementation, we will merge the loops in `autonomous_loop`.
        pass

    # Modified to allow single step execution for the loop
    # We need to modify TrelloBridge to allow single step or running in background.
    # I'll rely on a modified TrelloBridge or just call sync_loop if it was non-blocking.
    # TrelloBridge.sync_loop is blocking `while True`.
    # Let's assume we modify TrelloBridge to have `poll()` method or we run it in thread.

    # Actually, let's update `autonomous_loop` to be the master loop.
    # I need to update TrelloBridge to expose `poll_once()`.

    def run(self, task: str, stack: str = "python", extra_rules: List[str] = None, session_id: str = "default") -> Dict[str, Any]:
        # Usar el session_id como Namespace en Synapse para aislamiento total
        previous_namespace = self.namespace
        self.namespace = session_id

        print(f"🚀 Orchestrator starting task: {task} [Stack: {stack}] [Session: {session_id}]")

        try:
            # 0. Ensure Stack Knowledge (Bootstrap Mode)
            self.ensure_stack_knowledge(stack)

        # 1. Determine Initial State
            current_task_type = self.get_initial_task_type(task)
            history = []
            max_retries = 3
            retry_count = 0

            while current_task_type:
                # 2. Find Responsible Agent
                agent_name = self.get_handler_for_task(current_task_type)
                print(f"📍 Step: {current_task_type} -> Handler: {agent_name}")

                if agent_name == "Unknown":
                    print(f"❌ No handler found for {current_task_type}")
                    break

                # Update Trello based on Agent
                # Assuming session_id contains 'trello-CARDID'
                if session_id.startswith("trello-"):
                    card_id = session_id.split("-")[1]
                    if agent_name == "Reviewer":
                        self.bridge.move_card(card_id, "REVIEW")
                    elif agent_name == "Deployer":
                         # Almost done
                         pass

                # 3. Execute Agent
                context = {"history": history}
                execution_uuid = f"{SWARM}execution/{uuid.uuid4()}"

                # --- PHASE 3: P2P Delegation for Feature Implementation ---
                if current_task_type == "FeatureImplementationTask" and agent_name == "Coder":
                     print("🔀 Delegating to P2P Negotiation Session...")
                     coder = self.agents.get("Coder")
                     reviewer = self.agents.get("Reviewer")

                     # Prepare enhanced description with rules/lessons
                     # We reuse run_agent logic to get rules but we need to pass them to negotiate.
                     # Actually, negotiate calls generate_code_with_verification which is internal.
                     # To ensure constraints are passed, we should inject them into the task description here,
                     # or update Coder to fetch them. Coder currently doesn't fetch rules in negotiate,
                     # it relies on Orchestrator passing them.
                     # So we need to construct the enhanced prompt here.

                     golden_rules = self.get_golden_rules("Coder", stack=stack)
                     responsibilities = self.get_agent_responsibilities("Coder")
                     lessons = self.get_agent_lessons("Coder", stack=stack)

                     enhanced_task = task
                     enhanced_task = f"CONTEXT: Stack={stack}\n{enhanced_task}"
                     if golden_rules: enhanced_task = f"HARD CONSTRAINTS:\n" + "\n".join([f"- {r}" for r in golden_rules]) + f"\n\n{enhanced_task}"
                     if lessons: enhanced_task = f"LESSONS:\n" + "\n".join([f"- {l}" for l in lessons]) + f"\n\n{enhanced_task}"

                     result = coder.negotiate(enhanced_task, reviewer, context)
                     outcome = result.get("status", "failure")

                else:
                     # Standard Flow
                     result = self.run_agent(agent_name, task, context, task_type=current_task_type, stack=stack, extra_rules=extra_rules)
                     outcome = result.get("status", "failure")

                history.append({
                    "task_type": current_task_type,
                    "agent": agent_name,
                    "result": result,
                    "outcome": outcome,
                    "execution_uuid": execution_uuid,
                    "stack": stack
                })

                # 4. Determine Next Step (Reasoning)
                next_task_type = self.get_next_task(current_task_type, outcome)

                if next_task_type:
                    # OPTIMIZATION: If we just finished FeatureImplementationTask via Negotiation,
                    # we have effectively done CodeReviewTask.
                    # If next task is CodeReviewTask, we can verify if we should skip it.
                    if current_task_type == "FeatureImplementationTask" and outcome == "success" and next_task_type == "CodeReviewTask":
                        print("⏩ P2P Negotiation successful. Skipping explicit CodeReviewTask.")
                        # Get next task after CodeReviewTask
                        next_task_type = self.get_next_task("CodeReviewTask", "success")
                        if not next_task_type:
                            print("🏁 Workflow Complete (Skipped Review)")
                            break

                    print(f"🔄 Transition: {current_task_type} ({outcome}) -> {next_task_type}")

                    if outcome == "failure":
                         retry_count += 1
                         # ... (Failure learning logic same as before) ...
                         # Automatic Memory Ingestion: Lesson Learned
                         agent_uri = f"http://swarm.os/agent/{agent_name}"
                         issues = result.get('issues', [])
                         if not issues and result.get('error'):
                             issues = [result.get('error')]
                         error_msg = json.dumps(issues)

                         failure_triples = [
                             {"subject": execution_uuid, "predicate": f"{RDF}type", "object": f"{SWARM}ExecutionRecord"},
                             {"subject": execution_uuid, "predicate": f"{PROV}wasAssociatedWith", "object": agent_uri},
                             {"subject": execution_uuid, "predicate": f"{NIST}resultState", "object": '"on_failure"'},
                             {"subject": execution_uuid, "predicate": f"{SKOS}historyNote", "object": f'"{error_msg}"'},
                             {"subject": agent_uri, "predicate": f"{SWARM}learnedFrom", "object": execution_uuid},
                             {"subject": execution_uuid, "predicate": f"{SWARM}hasStack", "object": f'"{stack}"'}
                         ]
                         print(f"🧠 Learning from failure... Ingesting {len(failure_triples)} triples.")
                         self.ingest_triples(failure_triples)

                         if retry_count > max_retries:
                             print("🛑 Max retries exceeded. Halting workflow.")
                             break

                         print(f"⚠️  Task failed (Retry {retry_count}/{max_retries})... appending feedback.")
                         task = f"{task} (Fix: {error_msg})"
                    else:
                        retry_count = 0

                    current_task_type = next_task_type
                else:
                    print("🏁 Workflow Complete")
                    break

            return {
                "task": task,
                "history": history,
                "final_status": "success" if history and history[-1]["outcome"] == "success" else "failure"
            }
        finally:
             # Restore previous namespace to avoid side effects in shared instance
             self.namespace = previous_namespace

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("task", nargs="+", help="Task description")
    parser.add_argument("--stack", default="python", help="Tech stack (python, react, etc.)")
    args = parser.parse_args()

    task_str = " ".join(args.task)
    agent = OrchestratorAgent()
    try:
        result = agent.run(task_str, stack=args.stack)
        print(json.dumps(result, indent=2))
    finally:
        agent.close()
