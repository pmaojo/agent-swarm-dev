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
import subprocess
from typing import Dict, Any, Optional, List

# Add path to lib and agents
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SDK_PYTHON_PATH)
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
from llm import LLMService

# --- New Tool Imports ---
from agents.tools.definitions import TOOLS_SCHEMA
from agents.tools.files import read_file, write_file, list_dir
from agents.tools.patch import patch_file
from agents.tools.logs import read_logs
from agents.tools.shell import execute_command, run_shell_raw, CommandGuard
from agents.tools.context import ContextParser
from agents.tools.browser import BrowserTool
from lib.telemetry import report_thought, report_tool, report_event
from lib.contracts import EventType

# Namespaces
SWARM = "http://swarm.os/ontology/"

class CoderAgent:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50054"))
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

    def check_skill_unlocked(self, skill_id: str) -> bool:
        """Check if the agent has unlocked a specific skill in Synapse."""
        if not self.stub: return True
        query = f"""
        PREFIX swarm: <{SWARM}>
        ASK WHERE {{
            <{SWARM}agent/Coder> swarm:hasSkill <{SWARM}{skill_id}> .
        }}
        """
        try:
            res = self.stub.QuerySparql(semantic_engine_pb2.SparqlRequest(query=query, namespace="default"))
            data = json.loads(res.results_json)
            if isinstance(data, dict): return data.get("boolean", False)
            return False
        except Exception:
            return False

    def record_artifact(self, filename: str, content: str = "Modified via Tool"):
        """Record the generated artifact in Synapse."""
        if not self.stub: return
        subject = f"{SWARM}artifact/code/{int(time.time())}_{os.path.basename(filename)}"
        triples = [
            {"subject": subject, "predicate": f"{SWARM}type", "object": f"{SWARM}ArtifactType"},
            {"subject": subject, "predicate": f"{SWARM}description", "object": f'"{content}"'},
            {"subject": subject, "predicate": f"{SWARM}hasProperty", "object": f"{SWARM}prop/path/{filename}"},
        ]
        pb_triples = [semantic_engine_pb2.Triple(subject=t["subject"], predicate=t["predicate"], object=t["object"]) for t in triples]
        try:
            self.stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace))
        except Exception as e:
            print(f"⚠️ [Coder] Failed to record artifact: {e}")

    def record_negotiation(self, reviewer_agent: Any, execution_uuid: str):
        """Record P2P negotiation triple."""
        if not self.stub: return
        coder_uri = f"{SWARM}agent/Coder"
        reviewer_uri = f"{SWARM}agent/{reviewer_agent.__class__.__name__}" if reviewer_agent else f"{SWARM}agent/Reviewer"
        triples = [
            {"subject": coder_uri, "predicate": f"{SWARM}negotiatedWith", "object": reviewer_uri},
            {"subject": execution_uuid, "predicate": f"{SWARM}involvedInNegotiation", "object": coder_uri}
        ]
        pb_triples = [semantic_engine_pb2.Triple(subject=t["subject"], predicate=t["predicate"], object=t["object"]) for t in triples]
        try:
            self.stub.IngestTriples(semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace))
            print(f"🔗 [Coder] Recorded negotiation with Reviewer (Execution: {execution_uuid})")
        except Exception as e:
             print(f"⚠️ [Coder] Failed to record negotiation: {e}")

    def wait_for_approval(self, cmd_uuid: str, command: str) -> Dict[str, Any]:
        """Poll Synapse for command approval."""
        report_thought(f"COMMAND_SUSPENDED: Waiting for authorization on '{command}'", agent_id="Coder")
        print(f"⏳ [Coder] Waiting for approval for: '{command}' (UUID: {cmd_uuid})")
        guard = CommandGuard()
        start_time = time.time()
        while time.time() - start_time < 600:
            status = guard.check_status(cmd_uuid)
            if status == "APPROVED":
                print("✅ [Coder] Command APPROVED. Resuming execution...")
                return run_shell_raw(command)
            elif status == "REJECTED":
                print("⛔ [Coder] Command REJECTED by user.")
                return {"status": "failure", "error": "Command rejected by user."}
            time.sleep(5)
        return {"status": "failure", "error": "Approval timed out."}

    def _tool_file_ops(self, func_name: str, args: Dict) -> Any:
        if func_name == "read_file": return read_file(args.get("path"))
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
        elif func_name == "list_dir": return list_dir(args.get("path", "."))
        return None

    def _tool_sys_ops(self, func_name: str, args: Dict) -> Any:
        if func_name == "read_logs": return read_logs(args.get("path"), args.get("lines", 50), args.get("grep"))
        elif func_name == "execute_command": return execute_command(args.get("command"), args.get("reason"))
        elif func_name == "semantic_analysis":
            path = args.get("path")
            bridge_script = os.path.join(SDK_PYTHON_PATH, "..", "..", "scripts", "semantic_bridge.py")
            cmd = [sys.executable, bridge_script, path]
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                return {"status": "success", "message": f"Semantic analysis ingested for {path}"}
            except Exception as e:
                return {"status": "failure", "error": f"Semantic bridge failed: {e}"}
        return None

    def execute_tool(self, func_name: str, args: Dict) -> Any:
        """Dispatcher for tool execution."""
        msg = f"🔨 [Coder] Executing tool: {func_name} with args: {args}"
        print(msg)
        report_tool(func_name, args, agent_id="Coder")
        report_thought(f"Initiating {func_name} for mission objectives.", agent_id="Coder")
        try:
            res = self._tool_file_ops(func_name, args)
            if res is not None: return res
            
            res = self._tool_sys_ops(func_name, args)
            if res is not None: return res

            if func_name == "search_documentation": return self.browser.search_documentation(args.get("query"))
            elif func_name == "read_url": return self.browser.read_url(args.get("url"))
            else: return f"Error: Unknown tool '{func_name}'"
        except Exception as e:
            return f"Error executing tool '{func_name}': {e}"

    def _check_skills(self, task: str) -> str:
        """Check for required skills and modify task if locked."""
        if "TDD" in task.upper() or "TEST DRIVEN" in task.upper():
            if not self.check_skill_unlocked("tdd-level-2"):
                print("🔒 [Coder] Skill 'TDD Level 2' is LOCKED. Performing basic implementation instead.")
                return task + "\n[CONSTRAINT: TDD Level 2 is LOCKED. Do not use advanced mocking patterns.]"
            print("🔓 [Coder] Skill 'TDD Level 2' UNLOCKED. Advanced testing enabled.")
        return task

    def _prepare_mission_messages(self, task: str, context: Optional[Dict]) -> List[Dict]:
        """Construct the initial message list for the LLM."""
        system_prompt = """
        You are a Tactical Software Engineer Agent (CoderAgent).
        Guidelines: EXPLORE FIRST, SMART CONTEXT, RESEARCH, SURGICAL EDITS, TAGGING SKILL, TEST DRIVEN, SAFETY.
        When complete and VERIFIED, return a final text summary.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {self.context_parser.expand_context(task)}"}
        ]
        if context and context.get("history"):
            hist_msg = "History:\n" + "\n".join([f"- {h.get('outcome')}: {json.dumps(h.get('result', {}))}" for h in context["history"]])
            messages.append({"role": "user", "content": hist_msg})
            report_thought("Analyzing previous mission attempts for context.", agent_id="Coder")
        return messages

    def _process_tool_calls(self, tool_calls) -> List[Dict]:
        """Execute a list of tool calls and return responses."""
        responses = []
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}
            report_thought(f"Executing tool call: {func_name}", agent_id="Coder")
            result = self.execute_tool(func_name, args)
            if isinstance(result, dict) and result.get("status") == "pending_approval":
                result = self.wait_for_approval(result.get("uuid"), command=args.get('command'))
            report_thought(f"Tool {func_name} returned status: {result.get('status') if isinstance(result, dict) else 'success'}", agent_id="Coder")
            responses.append({
                "tool_call_id": tool_call.id, "role": "tool", "name": func_name,
                "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            })
        return responses

    def _execute_mission_step(self, messages) -> Any:
        """Single step of the LLM interaction."""
        response = self.llm.completion(prompt="", messages=messages, tools=TOOLS_SCHEMA, tool_choice="auto")
        if hasattr(response, "content") and response.content:
            report_thought(response.content, agent_id="Coder")
        return response

    def _handle_tool_responses(self, tool_calls, messages) -> bool:
        """Execute tools and update messages. Returns True if execution should stop (HALTED)."""
        tool_responses = self._process_tool_calls(tool_calls)
        for resp in tool_responses:
            if "SYSTEM_HALTED" in resp["content"]: return True
            messages.append(resp)
        return False

    def generate_code_with_verification(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Main Agent Loop using Tool Calling."""
        task = self._check_skills(task)
        messages = self._prepare_mission_messages(task, context)
        print(f"🧠 [Coder] Starting Task: {task[:50]}...")
        report_event(EventType.MISSION_ASSIGNED, f"Coder starting task: {task[:50]}...", details={"task": task})

        max_steps, step = 20, 0
        while step < max_steps:
            try:
                message_response = self._execute_mission_step(messages)
                messages.append(message_response.model_dump() if hasattr(message_response, "model_dump") else message_response)

                if hasattr(message_response, "tool_calls") and message_response.tool_calls:
                    if self._handle_tool_responses(message_response.tool_calls, messages):
                        return {"status": "failure", "error": "System Halted by tool output."}
                    step += len(message_response.tool_calls)
                else:
                    content = message_response.content if hasattr(message_response, "content") else str(message_response)
                    print("🏁 [Coder] Finished.")
                    return {"status": "success", "result": content, "saved_files": self.modified_files}
                step += 1
            except Exception as e:
                print(f"❌ [Coder] Error in loop: {e}")
                return {"status": "failure", "error": str(e)}
        return {"status": "failure", "error": "Max steps exceeded"}

    def research_stack(self, stack: str) -> List[str]:
        print(f"🔎 [Coder] Researching stack: {stack}...")
        system_prompt = "You are a Senior Tech Lead. Identify top 5 best practices for this stack. Return JSON: {'principles': []}."
        try:
            result = self.llm.get_structured_completion(f"Research: {stack}", system_prompt)
            return result.get("principles", [])[:5]
        except Exception as e:
            print(f"❌ [Coder] Research failed: {e}")
            return []

    def negotiate(self, task: str, reviewer_agent: Any, context: Dict) -> Dict[str, Any]:
        print("🤝 [Coder] Starting P2P Negotiation Session with Reviewer...")
        max_negotiations, negation_count = 3, 0
        execution_uuid = str(uuid.uuid4())
        while negation_count < max_negotiations:
            result = self.generate_code_with_verification(task, context)
            if result.get("status") == "failure": return result
            context["history"] = context.get("history", []) + [{
                "agent": "Coder", "outcome": "success", "result": result, "negotiation_round": negation_count
            }]
            print(f"📨 [Coder] Sending code to Reviewer (Round {negation_count+1})...")
            self.record_negotiation(reviewer_agent, execution_uuid)
            review_result = reviewer_agent.run(task, context)
            if review_result.get("status") == "success":
                print("✅ [Coder] Reviewer Approved!")
                return {"status": "success", "final_result": result, "review": review_result, "negotiations": negation_count + 1}
            issues = review_result.get("issues", [])
            print(f"🛑 [Coder] Reviewer Rejected: {issues}")
            task = f"{task}\n\nReviewer Feedback (Round {negation_count+1}):\n" + "\n".join(issues)
            negation_count += 1
        return {"status": "failure", "error": "Max negotiation rounds exhausted", "last_feedback": issues}

    def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        report_thought(f"ANALYZING_MISSION: {task}", agent_id="Coder")
        result = self.generate_code_with_verification(task, context)
        if "error" not in result:
             report_thought("MISSION_SUCCESS: Protocol completed. Results deployed.", agent_id="Coder")
        else:
             report_thought("NODE_ERROR: Protocol failed. Energy leakage detected.", agent_id="Coder")
        return {"status": "success" if "error" not in result else "failure", "task": task, "result": result}

if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List current directory"
    agent = CoderAgent()
    result = agent.run(task)
    print(json.dumps(result, indent=2))
