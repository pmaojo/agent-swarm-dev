import os
import subprocess
import yaml
import logging
import time
import requests
import sys
import uuid
import grpc
from typing import Optional

# Synapse Imports
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if SDK_PYTHON_PATH not in sys.path:
    sys.path.insert(0, SDK_PYTHON_PATH)
try:
    from synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        semantic_engine_pb2 = None
        semantic_engine_pb2_grpc = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ApiSandbox")

# Paths
ROOT_DIR = os.getcwd()
SANDBOX_DIR = os.path.join(ROOT_DIR, "openspec", "sandboxes")
# Try lib/bin first (symlink), then fallback to build dir
APICENTRIC_BIN_LINK = os.path.join(ROOT_DIR, "lib", "bin", "apicentric")
APICENTRIC_BIN_BUILD = os.path.join(ROOT_DIR, "apicentric_repo", "target", "release", "apicentric")

SIMULATOR_PORT = 9002  # Default port, but will be overridden by service definition
SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

class ApiSandboxTool:
    def __init__(self):
        os.makedirs(SANDBOX_DIR, exist_ok=True)
        self.simulator_process = None
        self.simulator_port = SIMULATOR_PORT  # Track actual simulator port
        self.binary_path = self._find_binary()

        # Synapse Connection
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
            logger.warning(f"⚠️ Failed to connect to Synapse: {e}")

    def ingest_lesson(self, failure_type: str, message: str):
        """Ingest failure as a Lesson Learned to block future attempts."""
        if not self.stub: return

        lesson_id = f"{SWARM}lesson/{uuid.uuid4()}"
        triples = [
            {"subject": lesson_id, "predicate": f"{RDF}type", "object": f"{SWARM}LessonLearned"},
            {"subject": lesson_id, "predicate": f"{SWARM}content", "object": f'"{message}"'},
            {"subject": lesson_id, "predicate": f"{NIST}resultState", "object": '"on_failure"'},
            {"subject": lesson_id, "predicate": f"{SWARM}context", "object": f'"{failure_type}"'}, # e.g. "missing_binary"
            {"subject": lesson_id, "predicate": f"{SWARM}source", "object": f"{SWARM}agent/ApiSandboxTool"}
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
            logger.info(f"🧠 Ingested Lesson Learned: {message}")
        except Exception as e:
            logger.error(f"❌ Failed to ingest lesson: {e}")

    def _find_binary(self) -> str:
        if os.path.exists(APICENTRIC_BIN_LINK):
            return APICENTRIC_BIN_LINK
        if os.path.exists(APICENTRIC_BIN_BUILD):
            return APICENTRIC_BIN_BUILD
        # Fallback to PATH
        import shutil
        path = shutil.which("apicentric")
        if path: return path

        logger.error(f"❌ Apicentric binary not found! checked: {APICENTRIC_BIN_LINK}, {APICENTRIC_BIN_BUILD}")
        return "apicentric" # Hope for the best

    def start_simulator_if_needed(self):
        """Checks if simulator is running, if not starts it."""
        # Check multiple possible ports for the simulator admin server
        possible_ports = [9002, 8000, 8080]
        simulator_running = False
        
        for port in possible_ports:
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=1)
                if response.status_code == 200:
                    logger.info(f"✅ Apicentric Simulator is already running on port {port}.")
                    self.simulator_port = port  # Store the actual port
                    simulator_running = True
                    break
            except requests.ConnectionError:
                continue
            except Exception as e:
                logger.debug(f"Port {port} check: {e}")
        
        if simulator_running:
            return
        
        logger.info(f"🚀 Starting Apicentric Simulator on default port {SIMULATOR_PORT}...")

        # Start in background
        cmd = [
            self.binary_path, "simulator", "start",
            "--services-dir", SANDBOX_DIR,
            # Port is now handled via apicentric.toml or default port range
            # "--watch" # Assume watch is supported or restart needed. Check help if needed.
        ]

        try:
            self.simulator_process = subprocess.Popen(
                cmd,
                stdout=open("apicentric_simulator.log", "a"),
                stderr=subprocess.STDOUT,
                cwd=ROOT_DIR
            )
            time.sleep(2) # Give it time to start
        except FileNotFoundError:
            logger.error(f"❌ Apicentric binary not found at {self.binary_path}")
        except Exception as e:
            logger.error(f"❌ Failed to start simulator: {e}")

    def stop_simulator(self):
        """Stops the simulator process if it was started by this tool."""
        if self.simulator_process:
            logger.info("🛑 Stopping Apicentric Simulator...")
            self.simulator_process.terminate()
            try:
                self.simulator_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.simulator_process.kill()
            self.simulator_process = None
        else:
            logger.info("ℹ️ Simulator was not started by this instance (or already stopped). Skipping cleanup.")

    def create_sandbox(self, spec_content: str, service_name: str) -> str:
        """
        Takes an OpenAPI spec content, creates a mock service, and returns the base URL.
        """
        self.start_simulator_if_needed()
        logger.info(f"🛠️ Creating API Sandbox for {service_name}...")

        # 1. Save spec to temp file
        # HACK: If spec doesn't have version, add it to avoid Apicentric failure
        if "openapi:" not in spec_content and "swagger:" not in spec_content:
            spec_content = "openapi: 3.0.0\n" + spec_content
        
        # Ensure info block exists (Apicentric requirement)
        if "info:" not in spec_content:
             spec_content += "\ninfo:\n  title: AutoGenerated\n  version: 1.0.0"
        
        # Ensure paths block exists (Apicentric/OpenAPI requirement)
        if "paths:" not in spec_content:
             spec_content += "\npaths: {}"
        
        spec_path = os.path.join(SANDBOX_DIR, f"{service_name}.openapi.yaml")
        with open(spec_path, "w") as f:
            f.write(spec_content)

        # 2. Run import to generate Apicentric YAML
        service_path = os.path.join(SANDBOX_DIR, f"{service_name}.yaml")
        cmd = [
            self.binary_path, "simulator", "import",
            "--file", spec_path,
            "--output", service_path
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"✅ Imported service {service_name}")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Import failed: {e.stderr}")
            return f"Error importing spec: {e.stderr}"
        except FileNotFoundError:
             msg = f"Apicentric binary missing at {self.binary_path}"
             logger.error(f"❌ {msg}")
             self.ingest_lesson("missing_binary", msg)
             return "Error: Apicentric binary missing."

        # 3. Get Base Path AND Port from generated YAML
        base_path = "/api"
        service_port = SIMULATOR_PORT  # Default to SIMULATOR_PORT
        try:
            with open(service_path, "r") as f:
                service_def = yaml.safe_load(f)
                base_path = service_def.get("server", {}).get("base_path", "/api")
                # Get the port from the service definition
                # apicentric assigns random ports in 8000-9000 range
                service_port = service_def.get("server", {}).get("port", SIMULATOR_PORT)
        except Exception as e:
            logger.warning(f"⚠️ Could not parse service definition, defaulting to port {SIMULATOR_PORT}: {e}")

        # Return mock URL using the actual service port
        mock_url = f"http://localhost:{service_port}{base_path}"
        logger.info(f"🌐 Mock available at {mock_url}")
        return mock_url

if __name__ == "__main__":
    # Test
    print("Testing ApiSandboxTool...")
    tool = ApiSandboxTool()
    try:
        sample_openapi = """
openapi: 3.0.0
info:
  title: Sample API
  version: 1.0.0
servers:
  - url: /api/v1
paths:
  /hello:
    get:
      summary: Say Hello
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  message:
                    type: string
                    example: "Hello World"
"""
        url = tool.create_sandbox(sample_openapi, "test-service")
        print(f"Result URL: {url}")
        time.sleep(2)
    finally:
        tool.stop_simulator()
