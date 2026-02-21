#!/usr/bin/env python3
"""
Orchestrator Agent - Task decomposition and workflow management.
Real implementation: Coordinates real agents via Synapse-driven state machine.
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

try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc

from coder import CoderAgent
from reviewer import ReviewerAgent
from deployer import DeployerAgent

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

    def ingest_triples(self, triples: List[Dict[str, str]], namespace: str = "default"):
        """Ingest triples helper"""
        if not self.stub: return
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        request = semantic_engine_pb2.IngestRequest(
            triples=pb_triples,
            namespace=namespace
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

    def query_graph(self, query: str) -> List[Dict]:
        """Execute SPARQL query against Synapse"""
        if not self.stub:
            print("❌ Not connected to Synapse")
            return []

        request = semantic_engine_pb2.SparqlRequest(
            query=query,
            namespace=self.namespace
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

    def get_agent_lessons(self, agent_name: str) -> List[str]:
        """Retrieve past lessons learned for this agent."""
        agent_uri = f"http://swarm.os/agent/{agent_name}"
        # Query for skos:historyNote via memory:learnedFrom
        # Filter out consolidated lessons
        query = f"""
        PREFIX swarm: <{SWARM}>
        PREFIX nist: <{NIST}>
        PREFIX skos: <{SKOS}>

        SELECT ?note
        WHERE {{
            <{agent_uri}> swarm:learnedFrom ?execId .
            ?execId skos:historyNote ?note .
            FILTER NOT EXISTS {{ ?execId swarm:isConsolidated "true" }}
        }}
        """
        results = self.query_graph(query)
        lessons = [r.get("?note") or r.get("note") for r in results]
        return lessons

    def get_golden_rules(self, agent_name: str) -> List[str]:
        """Retrieve Golden Rules (HardConstraints) for the agent's role."""
        agent_uri = f"http://swarm.os/agent/{agent_name}"
        # <Agent> a ?role . ?role nist:HardConstraint ?rule
        query = f"""
        PREFIX nist: <{NIST}>
        PREFIX rdf: <{RDF}>

        SELECT ?rule
        WHERE {{
            <{agent_uri}> rdf:type ?role .
            ?role nist:HardConstraint ?rule .
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

    def run_agent(self, agent_name: str, task_desc: str, context: Dict = None, task_type: str = None) -> Dict:
        """Execute an agent"""

        # 1. NIST Guardrail Check
        if task_type:
            if not self.check_compliance(agent_name, task_type):
                return {"status": "failure", "error": f"Security Violation: {agent_name} not authorized for {task_type}"}

        # 2. Dynamic System Prompts (Responsibilities)
        responsibilities = self.get_agent_responsibilities(agent_name)

        # 3. Lessons Learned (Memory)
        lessons = self.get_agent_lessons(agent_name)

        # 4. Golden Rules
        golden_rules = self.get_golden_rules(agent_name)

        # Inject into context/prompt
        # Since we can't easily change the agent's internal system prompt without modifying the agent,
        # we will append this information to the task description or context which the agent uses.
        # Ideally, we would pass this to the agent's run method if it supported 'system_context'.
        # For now, we prepend to task_desc which acts as the prompt input.

        enhanced_task_desc = f"{task_desc}"

        if golden_rules:
            enhanced_task_desc = f"⚠️ GOLDEN RULES (HARD CONSTRAINTS):\n" + "\n".join([f"- {r}" for r in golden_rules]) + f"\n\n{enhanced_task_desc}"

        if responsibilities:
            enhanced_task_desc = f"ROLE RESPONSIBILITIES:\n" + "\n".join([f"- {r}" for r in responsibilities]) + f"\n\n{enhanced_task_desc}"

        if lessons:
            enhanced_task_desc = f"LESSONS LEARNED FROM PAST FAILURES:\n" + "\n".join([f"- {l}" for l in lessons]) + f"\n\n{enhanced_task_desc}"

        print(f"🤖 Agent '{agent_name}' executing: {task_desc[:50]}...")
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

    def run(self, task: str) -> Dict[str, Any]:
        print(f"🚀 Orchestrator starting task: {task}")
        
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

            # 3. Execute Agent
            context = {"history": history}
            # Generate Execution UUID for this step
            execution_uuid = f"{SWARM}execution/{uuid.uuid4()}"

            result = self.run_agent(agent_name, task, context, task_type=current_task_type)
            outcome = result.get("status", "failure")

            history.append({
                "task_type": current_task_type,
                "agent": agent_name,
                "result": result,
                "outcome": outcome,
                "execution_uuid": execution_uuid
            })

            # 4. Determine Next Step (Reasoning)
            next_task_type = self.get_next_task(current_task_type, outcome)

            if next_task_type:
                print(f"🔄 Transition: {current_task_type} ({outcome}) -> {next_task_type}")

                if outcome == "failure":
                     retry_count += 1

                     # Automatic Memory Ingestion: Lesson Learned
                     # [Execution_UUID] prov:wasAssociatedWith [Agent_ID]
                     # [Execution_UUID] nist:resultState "on_failure"
                     # [Execution_UUID] skos:historyNote "[The critique/error message from the Reviewer]"
                     # [Agent_ID] memory:learnedFrom [Execution_UUID]

                     agent_uri = f"http://swarm.os/agent/{agent_name}"

                     # Extract error message
                     issues = result.get('issues', [])
                     if not issues and result.get('error'):
                         issues = [result.get('error')]
                     error_msg = json.dumps(issues)

                     failure_triples = [
                         {"subject": execution_uuid, "predicate": f"{RDF}type", "object": f"{SWARM}ExecutionRecord"},
                         {"subject": execution_uuid, "predicate": f"{PROV}wasAssociatedWith", "object": agent_uri},
                         # Wrap resultState and historyNote in QUOTES to store as Literals
                         {"subject": execution_uuid, "predicate": f"{NIST}resultState", "object": '"on_failure"'},
                         {"subject": execution_uuid, "predicate": f"{SKOS}historyNote", "object": f'"{error_msg}"'},
                         {"subject": agent_uri, "predicate": f"{SWARM}learnedFrom", "object": execution_uuid}
                     ]

                     print(f"🧠 Learning from failure... Ingesting {len(failure_triples)} triples.")
                     self.ingest_triples(failure_triples)

                     if retry_count > max_retries:
                         print("🛑 Max retries exceeded. Halting workflow.")
                         break

                     print(f"⚠️  Task failed (Retry {retry_count}/{max_retries})... appending feedback to instructions.")

                     # Be more verbose in feedback
                     task = f"{task} (Fix previous issues: {error_msg})"
                else:
                    # Reset retry count on success
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

if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Implement feature X"
    agent = OrchestratorAgent()
    try:
        result = agent.run(task)
        print(json.dumps(result, indent=2))
    finally:
        agent.close()
