#!/usr/bin/env python3
"""
Coder Agent - Tactical Operator for Code & System Operations.
Real implementation using LLM Tool Calling and Synapse Memory.
Enhanced for NIST Guardrails and Autonomous Operations (Phase 3).
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

# --- New Tool Imports ---
from agents.tools.definitions import TOOLS_SCHEMA
from agents.tools.files import read_file, write_file, list_dir
from agents.tools.patch import patch_file
from agents.tools.logs import read_logs
from agents.tools.shell import execute_command, run_shell_raw, CommandGuard

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

    def record_artifact(self, filename: str, content: str = "Modified via Tool"):
        """Record the generated artifact in Synapse."""
        if not self.stub: return

        subject = f"{SWARM}artifact/code/{int(time.time())}_{os.path.basename(filename)}"
        triples = [
            {"subject": subject, "predicate": f"{SWARM}type", "object": f"{SWARM}ArtifactType"},
            {"subject": subject, "predicate": f"{SWARM}description", "object": "Generated/Modified Code"},
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

    def wait_for_approval(self, cmd_uuid: str, command: str) -> Dict[str, Any]:
        """Poll Synapse for command approval."""
        print(f"⏳ [Coder] Waiting for approval for: '{command}' (UUID: {cmd_uuid})")
        print("   -> Reply via Telegram: /approve <UUID>")

        guard = CommandGuard()
        start_time = time.time()
        timeout = 600 # 10 minutes timeout

        while time.time() - start_time < timeout:
            status = guard.check_status(cmd_uuid)
            if status == "APPROVED":
                print("✅ [Coder] Command APPROVED. Resuming execution...")
                return run_shell_raw(command)
            elif status == "REJECTED":
                print("⛔ [Coder] Command REJECTED by user.")
                return {"status": "failure", "error": "Command rejected by user."}

            time.sleep(5) # Poll every 5s

        return {"status": "failure", "error": "Approval timed out."}

    def execute_tool(self, func_name: str, args: Dict) -> Any:
        """Dispatcher for tool execution."""
        print(f"🔨 [Coder] Executing tool: {func_name} with args: {args}")

        try:
            if func_name == "read_file":
                return read_file(args.get("path"))
            elif func_name == "write_file":
                result = write_file(args.get("path"), args.get("content"))
                self.record_artifact(args.get("path"), args.get("content"))
                return result
            elif func_name == "patch_file":
                result = patch_file(args.get("path"), args.get("search_content"), args.get("replace_content"))
                # Ideally record artifact too? content is unknown unless we read it back.
                return result
            elif func_name == "list_dir":
                return list_dir(args.get("path", "."))
            elif func_name == "read_logs":
                return read_logs(args.get("path"), args.get("lines", 50), args.get("grep"))
            elif func_name == "execute_command":
                return execute_command(args.get("command"), args.get("reason"))
            else:
                return f"Error: Unknown tool '{func_name}'"
        except Exception as e:
            return f"Error executing tool '{func_name}': {e}"

    def generate_code_with_verification(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main Agent Loop using Tool Calling.
        """
        print(f"🧠 [Coder] Starting Task: {task[:50]}...")

        system_prompt = """
        You are a Tactical Software Engineer Agent (CoderAgent).
        You have direct access to the filesystem and shell.

        Your Goal: Implement the requested feature or fix completely.

        Guidelines:
        1. EXPLORE FIRST: Use `list_dir` and `read_file` to understand the codebase.
        2. TEST DRIVEN: Create or update tests before or along with your changes.
        3. VERIFY: You MUST run verification commands (e.g., `pytest`, `npm test`) using `execute_command`.
        4. EDIT SMART: Use `patch_file` for partial edits to avoid overwriting large files. Use `write_file` for new files.
        5. DEBUG: If a test fails, use `read_logs` or read the output, fix the code, and retry.
        6. SAFETY: Dangerous commands (rm, npm install) require human approval. Provide a good reason.

        When you are confident the task is complete and VERIFIED, return a final text summary.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task}"}
        ]

        # Add history from context if available
        if context and context.get("history"):
            hist_msg = "History of previous attempts:\n"
            for h in context["history"]:
                hist_msg += f"- {h.get('outcome')}: {json.dumps(h.get('result', {}))}\n"
            messages.append({"role": "user", "content": hist_msg})

        max_steps = 15 # Limit tool steps to avoid infinite loops
        step = 0

        while step < max_steps:
            try:
                # Call LLM
                completion_msg = self.llm.completion(
                    prompt="", # Prompt is in messages
                    messages=messages, # We need to pass full messages list
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto"
                )

                # Check if we got a tool call or final text
                # My llm.completion returns message object if tools used, or content string if not?
                # Wait, my llm.completion implementation:
                # if tools: return response.choices[0].message
                # else: return content
                # But here I am calling it with tools=TOOLS_SCHEMA.
                # So it returns message object.

                message = completion_msg
                messages.append(message) # Append assistant's response to history

                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        step += 1
                        func_name = tool_call.function.name
                        try:
                            args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            args = {}

                        # Execute
                        result = self.execute_tool(func_name, args)

                        # Handle Pending Approval
                        if isinstance(result, dict) and result.get("status") == "pending_approval":
                            uuid_val = result.get("uuid")
                            result = self.wait_for_approval(uuid_val, command=args.get('command'))

                        # Feed back result
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        })
                else:
                    # No tool calls -> Final response (or just text)
                    content = message.content
                    print("🏁 [Coder] Finished.")
                    return {"status": "success", "result": content, "saved_files": []} # We don't track saved files list explicitly anymore unless we scan history

            except Exception as e:
                print(f"❌ [Coder] Error in loop: {e}")
                return {"status": "failure", "error": str(e)}

        return {"status": "failure", "error": "Max steps exceeded"}

    def research_stack(self, stack: str) -> List[str]:
        # Reuse existing research logic but maybe using tools?
        # For now keep legacy JSON mode for research as it's pure knowledge query.
        print(f"🔎 [Coder] Researching stack: {stack}...")
        system_prompt = "You are a Senior Tech Lead. Identify top 5 best practices for this stack. Return JSON: {'principles': []}."
        try:
            result = self.llm.get_structured_completion(f"Research: {stack}", system_prompt)
            return result.get("principles", [])[:5]
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
            # 1. Generate & Self-Verify (Using Tool Loop)
            result = self.generate_code_with_verification(task, context)

            if result.get("status") == "failure":
                 # Failed self-correction, return failure
                 return result

            # 2. Update Context for Reviewer
            step_record = {
                "agent": "Coder",
                "outcome": "success",
                "result": result, # Now text summary
                "negotiation_round": negotiation_count
            }
            context["history"] = context.get("history", []) + [step_record]

            # 3. Call Reviewer (Directly)
            print(f"📨 [Coder] Sending code to Reviewer (Round {negotiation_count+1})...")
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
            task = f"{task}\n\nReviewer Feedback (Round {negotiation_count+1}):\n" + "\n".join(issues)
            negotiation_count += 1

        return {
            "status": "failure",
            "error": "Max negotiation rounds exhausted",
            "last_feedback": issues
        }

    def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        result = self.generate_code_with_verification(task, context)
        return {
            "status": "success" if "error" not in result else "failure",
            "task": task,
            "result": result
        }

if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List current directory"
    agent = CoderAgent()
    result = agent.run(task)
    print(json.dumps(result, indent=2))
