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

# Add path to proto for generated code imports
proto_dir = os.path.join(os.path.dirname(__file__), 'proto')
if proto_dir not in sys.path:
    sys.path.insert(0, proto_dir)

try:
    from synapse.infrastructure.web import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        try:
            from proto import semantic_engine_pb2, semantic_engine_pb2_grpc
        except ImportError:
            semantic_engine_pb2 = None
            semantic_engine_pb2_grpc = None
from llm import LLMService

# --- New Tool Imports ---
from agents.tools.definitions import TOOLS_SCHEMA
from agents.tools.files import read_file, write_file, list_dir
from agents.tools.patch import patch_file
from agents.tools.logs import read_logs
from agents.tools.shell import execute_command, run_shell_raw, CommandGuard
from agents.tools.context import ContextParser
from agents.tools.browser import BrowserTool

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
        self.context_parser = ContextParser()
        self.browser = BrowserTool()
        self.modified_files = []
        self.connect()

    def connect(self):
        if not semantic_engine_pb2_grpc:
            print("⚠️ [Coder] Synapse gRPC modules not found. Tracking disabled.")
            return
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"❌ [Coder] Failed to connect to Synapse: {e}")

    def close(self):
        if self.channel:
            self.channel.close()
        self.browser.close()
        self.context_parser.close()

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
                path = args.get("path")
                result = write_file(path, args.get("content"))
                self.record_artifact(path, args.get("content"))
                if path not in self.modified_files: self.modified_files.append(path)
                return result
            elif func_name == "patch_file":
                path = args.get("path")
                result = patch_file(path, args.get("search_content"), args.get("replace_content"))
                if path not in self.modified_files: self.modified_files.append(path)
                return result
            elif func_name == "list_dir":
                return list_dir(args.get("path", "."))
            elif func_name == "read_logs":
                return read_logs(args.get("path"), args.get("lines", 50), args.get("grep"))
            elif func_name == "execute_command":
                return execute_command(args.get("command"), args.get("reason"))
            elif func_name == "search_documentation":
                return self.browser.search_documentation(args.get("query"))
            elif func_name == "read_url":
                return self.browser.read_url(args.get("url"))
            else:
                return f"Error: Unknown tool '{func_name}'"
        except Exception as e:
            return f"Error executing tool '{func_name}': {e}"

    def generate_code_with_verification(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main Agent Loop using Tool Calling.
        """
        # Expand Context using Smart Context Parser
        task_with_context = self.context_parser.expand_context(task)

        print(f"🧠 [Coder] Starting Task: {task[:50]}...")

        system_prompt = """
        You are a Tactical Software Engineer Agent (CoderAgent).
        You have direct access to the filesystem, shell, and internet (via BrowserTool).

        Your Goal: Implement the requested feature or fix completely.

        Guidelines:
        1. EXPLORE FIRST: Use `list_dir` and `read_file` to understand the codebase.
        2. SMART CONTEXT: If you see @file:path in the prompt, the content is already provided below.
        3. RESEARCH: If you encounter an error or need documentation, use `search_documentation` and `read_url`. Do not guess.
        4. SURGICAL EDITS: Use `patch_file` for partial edits. Only use `write_file` for new files or complete rewrites.
        5. TAGGING SKILL: When you discover a new constraint or best practice, add a comment in the code:
           `// @synapse:constraint Always use X for Y`
           This helps the Swarm learn.
        6. TEST DRIVEN: Create or update tests. Verify with `pytest` or `npm test`.
        7. SAFETY: Dangerous commands (rm, npm install) require approval.

        When you are confident the task is complete and VERIFIED, return a final text summary.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task_with_context}"}
        ]

        # Add history from context if available
        if context and context.get("history"):
            hist_msg = "History of previous attempts:\n"
            for h in context["history"]:
                hist_msg += f"- {h.get('outcome')}: {json.dumps(h.get('result', {}))}\n"
            messages.append({"role": "user", "content": hist_msg})

        max_steps = 20 # Limit tool steps
        step = 0

        while step < max_steps:
            try:
                # Call LLM
                completion_msg = self.llm.completion(
                    prompt="",
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto"
                )

                message = completion_msg
                messages.append(message)

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

                        # Check for SYSTEM_HALTED (Kill Switch)
                        if isinstance(result, dict) and "SYSTEM_HALTED" in str(result.get("error", "")):
                            print("🛑 [Coder] System Halted. Aborting execution loop.")
                            return {"status": "failure", "error": result["error"]}

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
                    content = message.content
                    print("🏁 [Coder] Finished.")
                    return {"status": "success", "result": content, "saved_files": self.modified_files}

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
