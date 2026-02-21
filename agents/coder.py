#!/usr/bin/env python3
"""
Coder Agent - Code generation based on specifications and feedback.
Real implementation using LLM and Synapse Memory.
Enhanced for P2P Negotiation and Self-Correction (Phase 3).
"""
import os
import json
import grpc
import sys
import time
import uuid
from typing import Dict, Any, Optional, List

# Add path to lib and root for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        from proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from llm import LLMService

try:
    from agents.tools.executor import run_command
except ImportError:
    # Fallback for different execution contexts
    from tools.executor import run_command

# Namespaces
SWARM = "http://swarm.os/ontology/"

class CoderAgent:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.namespace = "default"
        self.llm = LLMService()
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"❌ [Coder] Failed to connect to Synapse: {e}")

    def close(self):
        if self.channel:
            self.channel.close()

    def query_critiques(self, task_description: str) -> List[str]:
        """Query Synapse for past critiques related to this task context."""
        if not self.stub: return []
        
        query = f"""
        SELECT ?message
        WHERE {{
            ?critique <{SWARM}type> <{SWARM}ArtifactType> .
            ?critique <{SWARM}description> "Feedback from Reviewer explaining why code was rejected." .
            ?critique <{SWARM}hasProperty> ?prop .
            ?prop <{SWARM}message> ?message .
        }}
        LIMIT 5
        """
        try:
            request = semantic_engine_pb2.SparqlRequest(query=query, namespace=self.namespace)
            response = self.stub.QuerySparql(request)
            results = json.loads(response.results_json)
            return [r.get("message", "") for r in results if r.get("message")]
        except Exception as e:
            print(f"⚠️ [Coder] Failed to query critiques: {e}")
            return []

    def record_artifact(self, filename: str, content: str):
        """Record the generated artifact in Synapse."""
        if not self.stub: return

        subject = f"{SWARM}artifact/code/{int(time.time())}_{os.path.basename(filename)}"
        triples = [
            {"subject": subject, "predicate": f"{SWARM}type", "object": f"{SWARM}ArtifactType"},
            {"subject": subject, "predicate": f"{SWARM}description", "object": "Generated Code"},
            {"subject": subject, "predicate": f"{SWARM}hasProperty", "object": f"{SWARM}prop/path/{filename}"},
        ]

        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))

        try:
            self.stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace))
        except Exception as e:
            print(f"⚠️ [Coder] Failed to record artifact: {e}")

    def record_negotiation(self, reviewer_agent: Any, execution_uuid: str):
        """Record P2P negotiation triple."""
        if not self.stub: return

        coder_uri = f"{SWARM}agent/Coder"
        reviewer_uri = f"{SWARM}agent/Reviewer"

        triples = [
            {"subject": coder_uri, "predicate": f"{SWARM}negotiatedWith", "object": reviewer_uri},
            {"subject": execution_uuid, "predicate": f"{SWARM}involvedInNegotiation", "object": coder_uri}
        ]

        pb_triples = []
        for t in triples:
             pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))

        try:
            self.stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace))
            print(f"🔗 [Coder] Recorded negotiation with Reviewer (Execution: {execution_uuid})")
        except Exception as e:
             print(f"⚠️ [Coder] Failed to record negotiation: {e}")


    def generate_code_with_verification(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate code, run verification tool, and retry if needed (Self-Correction Loop).
        """
        attempts = 0
        max_attempts = 2
        history = context.get('history', []) if context else []
        current_feedback = ""

        while attempts <= max_attempts:
            print(f"🧠 [Coder] Generating code (Attempt {attempts+1})...")

            # Construct Prompt
            system_prompt = """
            You are an expert Python software engineer.
            Your task is to implement the requested feature.

            You have access to a Test Runner tool. You MUST generate a verification command to test your code.

            Return ONLY a JSON object with the following structure:
            {
                "files": [
                    {
                        "path": "path/to/file.py",
                        "content": "full source code"
                    }
                ],
                "dependencies": ["list", "of", "pip", "packages"],
                "verification_command": "python3 -m unittest tests/test_feature.py" or "pytest"
            }

            If you need to create a test file to run the verification, include it in the "files" list.
            Ensure code is complete, correct, and follows best practices.
            """

            prompt = f"Task: {task}\n"
            if current_feedback:
                prompt += f"\n⚠️ Previous attempt failed verification:\n{current_feedback}\nFix the code.\n"

            # Include global history
            if history:
                 prompt += "\nHistory of previous external attempts:\n"
                 for h in history:
                     prompt += f"- {h.get('outcome')}: {json.dumps(h.get('result', {}))}\n"

            # Call LLM
            try:
                result = self.llm.get_structured_completion(prompt, system_prompt)
            except Exception as e:
                return {"status": "failure", "error": f"LLM Error: {e}"}

            generated_files = result.get("files", [])
            verification_cmd = result.get("verification_command")

            if not generated_files:
                return {"status": "failure", "error": "No files generated"}

            # Write files to disk
            saved_files = []
            for file_data in generated_files:
                path = file_data.get("path")
                content = file_data.get("content")
                if path and content:
                    dir_path = os.path.dirname(path)
                    if dir_path and not os.path.exists(dir_path):
                        os.makedirs(dir_path)
                    with open(path, "w") as f:
                        f.write(content)
                    saved_files.append(path)
                    self.record_artifact(path, content)

            print(f"✍️ [Coder] Wrote {len(saved_files)} files.")

            # Run Verification
            if verification_cmd:
                print(f"🧪 [Coder] Running verification: {verification_cmd}")
                code, stdout, stderr = run_command(verification_cmd)

                if code != 0:
                    print(f"❌ [Coder] Verification Failed (Exit Code {code})")
                    current_feedback = f"Command: {verification_cmd}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                    attempts += 1
                    continue # Retry loop
                else:
                    print(f"✅ [Coder] Verification Passed!")
            else:
                print("⚠️ [Coder] No verification command provided. Skipping self-correction.")

            # If we get here, success or no verification
            result["saved_files"] = saved_files
            return result

        return {"status": "failure", "error": "Max self-correction attempts exceeded", "details": current_feedback}

    def research_stack(self, stack: str) -> List[str]:
        """
        Research a new stack and return 5 best practices/principles.
        """
        print(f"🔎 [Coder] Researching stack: {stack}...")

        system_prompt = """
        You are a Senior Tech Lead researching a new technology stack.
        Your goal is to identify the top 5 most critical best practices, principles, or hard constraints
        for writing high-quality, secure code in this stack.

        Return a JSON object:
        {
            "principles": [
                "Principle 1 description...",
                "Principle 2 description...",
                "Principle 3 description...",
                "Principle 4 description...",
                "Principle 5 description..."
            ]
        }
        """

        prompt = f"Research the technology stack: {stack}"

        try:
            result = self.llm.get_structured_completion(prompt, system_prompt)
            principles = result.get("principles", [])
            return principles[:5]
        except Exception as e:
            print(f"❌ [Coder] Research failed: {e}")
            return []

    def negotiate(self, task: str, reviewer_agent: Any, context: Dict) -> Dict[str, Any]:
        """
        P2P Negotiation Loop with Reviewer.
        Delegated by Orchestrator.
        """
        print("🤝 [Coder] Starting P2P Negotiation Session with Reviewer...")
        max_negotiations = 3
        negotiation_count = 0
        execution_uuid = str(uuid.uuid4()) # Traceability for this session

        while negotiation_count < max_negotiations:
            # 1. Generate & Self-Verify
            result = self.generate_code_with_verification(task, context)

            if result.get("status") == "failure":
                 # Failed self-correction, return failure
                 return result

            # 2. Update Context for Reviewer
            # We add our result to the history so Reviewer can see it
            step_record = {
                "agent": "Coder",
                "outcome": "success",
                "result": result,
                "negotiation_round": negotiation_count
            }
            context["history"] = context.get("history", []) + [step_record]

            # 3. Call Reviewer (Directly)
            print(f"📨 [Coder] Sending code to Reviewer (Round {negotiation_count+1})...")

            # Record Traceability Triple
            self.record_negotiation(reviewer_agent, execution_uuid)

            review_result = reviewer_agent.run(task, context)

            outcome = review_result.get("status")
            if outcome == "success":
                print("✅ [Coder] Reviewer Approved!")
                return {
                    "status": "success",
                    "final_result": result,
                    "review": review_result,
                    "negotiations": negotiation_count + 1
                }

            # 4. Handle Rejection
            issues = review_result.get("issues", [])
            print(f"🛑 [Coder] Reviewer Rejected: {issues}")

            # Update task description with feedback for next iteration
            task = f"{task}\n\nReviewer Feedback (Round {negotiation_count+1}):\n" + "\n".join(issues)
            negotiation_count += 1

        return {
            "status": "failure",
            "error": "Max negotiation rounds exhausted",
            "last_feedback": issues
        }

    def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        # Legacy run method, mainly for simple tasks or if Orchestrator calls it directly without negotiation
        # Use generate_code_with_verification for robustness
        result = self.generate_code_with_verification(task, context)
        return {
            "status": "success" if "error" not in result else "failure",
            "task": task,
            "result": result
        }

if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Create a hello world python script"
    agent = CoderAgent()
    result = agent.run(task)
    print(json.dumps(result, indent=2))
