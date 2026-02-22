"""
Shell Command Execution with NIST Guardrails.
"""
import os
import sys
import uuid
import grpc
import subprocess
import requests
import json
from typing import Dict, Any, Optional

# --- Synapse/Proto Imports ---
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if SDK_PYTHON_PATH not in sys.path:
    sys.path.insert(0, SDK_PYTHON_PATH)
    # Ensure sub-modules are discoverable
    sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "lib"))
    sys.path.insert(0, os.path.join(SDK_PYTHON_PATH, "agents"))

try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        semantic_engine_pb2 = None
        semantic_engine_pb2_grpc = None
        print("⚠️ Warning: Synapse protobufs not found. Guardrails disabled (Safe Mode only).")

# --- Constants ---
NIST = "http://nist.gov/caisi/"
SWARM = "http://swarm.os/ontology/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
PROV = "http://www.w3.org/ns/prov#"

SAFE_COMMANDS = ["ls", "grep", "cat", "echo", "pwd", "whoami", "date", "head", "tail", "find", "stat", "diff", "npm", "pytest", "python", "python3", "node", "false", "sleep", "pylint", "flake8", "bandit"]
RESTRICTED_PATTERNS = ["rm ", "sudo", "chmod", "chown", "mv ", "cp ", "dd ", "mkfs", "mount", "umount", "systemctl", "service", "kill", "pkill", "killall", "apt", "apt-get", "yum", "dnf", "npm install", "pip install", "docker", "docker-compose", "kubectl", "git push", "wget", "curl", "ssh", "scp", "nc", "ncat", "netcat", ">", ">>"]
# Redirects are tricky but > can overwrite files. `write_file` is safer.
# We block redirects in restricted mode.

class CommandGuard:
    def __init__(self):
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.connect()

    def connect(self):
        if not semantic_engine_pb2_grpc: return
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"❌ Failed to connect to Synapse: {e}")

    def ingest_request(self, cmd_uuid: str, command: str, reason: str):
        if not self.stub: return

        triples = [
            {"subject": cmd_uuid, "predicate": f"{RDF}type", "object": f"{NIST}CommandRequest"},
            {"subject": cmd_uuid, "predicate": f"{NIST}commandContent", "object": f'"{command}"'},
            {"subject": cmd_uuid, "predicate": f"{NIST}approvalStatus", "object": '"PENDING"'},
            {"subject": cmd_uuid, "predicate": f"{NIST}requestReason", "object": f'"{reason}"'},
            {"subject": cmd_uuid, "predicate": f"{SWARM}requestedBy", "object": f"{SWARM}agent/Coder"}
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
            print(f"❌ Failed to ingest command request: {e}")

    def check_status(self, cmd_uuid: str) -> str:
        if not self.stub: return "UNKNOWN"

        query = f"""
        SELECT ?status
        WHERE {{
            <{cmd_uuid}> <{NIST}approvalStatus> ?status .
        }}
        """
        request = semantic_engine_pb2.SparqlRequest(query=query, namespace="default")
        try:
            response = self.stub.QuerySparql(request)
            results = json.loads(response.results_json)
            if results:
                return results[0].get("?status") or results[0].get("status")
        except Exception:
            pass
        return "PENDING"

    def check_kill_switch(self) -> bool:
        """
        Check global system status. Returns True if HALTED.
        Uses optimized ASK query to detect HALTED state without subsequent OPERATIONAL state.
        """
        if not self.stub: return False # If synapse down, default to safe (or risk it? default to operational is standard)

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

        try:
            request = semantic_engine_pb2.SparqlRequest(query=query, namespace="default")
            response = self.stub.QuerySparql(request)
            result_json = json.loads(response.results_json)

            # Handle potential list response (if Synapse treats ASK oddly or returns empty set)
            if isinstance(result_json, dict):
                is_halted = result_json.get("boolean", False)
            elif isinstance(result_json, list) and result_json and isinstance(result_json[0], dict):
                # Fallback if wrapped in list
                is_halted = result_json[0].get("boolean", False)
            else:
                is_halted = False

            if is_halted:
                print("🛑 SYSTEM HALTED (Kill Switch Active)")
            return is_halted
        except Exception as e:
            print(f"⚠️ Failed to check kill switch: {e}")
            return False

def send_telegram_alert(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ Telegram not configured.")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Telegram alert failed: {e}")

def is_safe(command: str) -> bool:
    # 1. Exact match safe commands
    parts = command.strip().split()
    if not parts: return False
    cmd = parts[0]

    # 2. Check restricted patterns
    for p in RESTRICTED_PATTERNS:
        if p in command: # Simple substring check is strict but safer
            return False

    # 3. Check explicitly safe list
    if cmd in SAFE_COMMANDS:
        # Check for dangerous flags? grep is safe, but grep > file is not.
        if ">" in command: return False
        return True

    return False # Default deny if not in safe list? Or check if in Restricted?
    # User said: "Safe: ... Restricted: ..."
    # We default to restricted for anything else?
    # Better to default to restricted.
    return False

def run_shell_raw(command: str, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Raw execution without guardrails (for approved commands)."""
    try:
        # Use shell=True for complex commands (pipes, etc)
        # Security Note: Only call this for SAFE or APPROVED commands.
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120, env=run_env)
        return {
            "status": "success" if result.returncode == 0 else "failure",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        return {"status": "failure", "error": str(e)}

def execute_command(command: str, reason: str = "Task execution", env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Execute a shell command with guardrails.
    Returns a dict with 'status' (success, failure, pending_approval) and 'output' or 'uuid'.
    """
    guard = CommandGuard()

    # 0. Kill Switch Check (High Granularity)
    if guard.check_kill_switch():
         return {
             "status": "failure",
             "error": "SYSTEM_HALTED: Kill switch active. Execution denied. DO NOT RETRY until system is resumed."
         }

    if is_safe(command):
        print(f"✅ Executing Safe Command: {command}")
        return run_shell_raw(command, env=env)
    else:
        print(f"🛑 Restricted Command Detected: {command}")
        cmd_uuid = f"{NIST}request/{uuid.uuid4()}"

        # 1. Ingest Request
        guard.ingest_request(cmd_uuid, command, reason)

        # 2. Notify
        msg = f"🛑 **Approval Needed**\nCommand: `{command}`\nReason: {reason}\nUUID: `{cmd_uuid}`\n\nReply `/approve {cmd_uuid}` or `/deny {cmd_uuid}`"
        send_telegram_alert(msg)

        return {
            "status": "pending_approval",
            "uuid": cmd_uuid,
            "message": "Command requires approval. Notification sent. Waiting for status change."
        }
