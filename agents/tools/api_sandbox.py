import os
import subprocess
import yaml
import logging
import time
import requests
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ApiSandbox")

# Paths
ROOT_DIR = os.getcwd()
SANDBOX_DIR = os.path.join(ROOT_DIR, "openspec", "sandboxes")
APICENTRIC_BIN = os.path.join(ROOT_DIR, "apicentric_repo", "target", "release", "apicentric")
SIMULATOR_PORT = 9002

class ApiSandboxTool:
    def __init__(self):
        os.makedirs(SANDBOX_DIR, exist_ok=True)
        self.simulator_process = None
        self.start_simulator_if_needed()

    def start_simulator_if_needed(self):
        """Checks if simulator is running, if not starts it."""
        try:
            # Check if port is open
            response = requests.get(f"http://localhost:{SIMULATOR_PORT}/health", timeout=1)
            if response.status_code == 200:
                logger.info("✅ Apicentric Simulator is already running.")
                return
        except requests.ConnectionError:
            pass
        except Exception as e:
            logger.warning(f"⚠️ Failed to connect to simulator: {e}")

        logger.info(f"🚀 Starting Apicentric Simulator on port {SIMULATOR_PORT}...")

        # Start in background
        cmd = [
            APICENTRIC_BIN, "simulator", "start",
            "--services-dir", SANDBOX_DIR,
            "--port", str(SIMULATOR_PORT),
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
            logger.error(f"❌ Apicentric binary not found at {APICENTRIC_BIN}")
        except Exception as e:
            logger.error(f"❌ Failed to start simulator: {e}")

    def create_sandbox(self, spec_content: str, service_name: str) -> str:
        """
        Takes an OpenAPI spec content, creates a mock service, and returns the base URL.
        """
        logger.info(f"🛠️ Creating API Sandbox for {service_name}...")

        # 1. Save spec to temp file
        spec_path = os.path.join(SANDBOX_DIR, f"{service_name}.openapi.yaml")
        with open(spec_path, "w") as f:
            f.write(spec_content)

        # 2. Run import to generate Apicentric YAML
        service_path = os.path.join(SANDBOX_DIR, f"{service_name}.yaml")
        cmd = [
            APICENTRIC_BIN, "simulator", "import",
            "--file", spec_path,
            "--output", service_path
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"✅ Imported service {service_name}")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Import failed: {e.stderr}")
            return f"Error importing spec: {e.stderr}"
        except FileNotFoundError:
             logger.error(f"❌ Apicentric binary not found at {APICENTRIC_BIN}")
             return "Error: Apicentric binary missing."

        # 3. Get Base Path from generated YAML
        base_path = "/api"
        try:
            with open(service_path, "r") as f:
                service_def = yaml.safe_load(f)
                base_path = service_def.get("server", {}).get("base_path", "/api")
        except Exception as e:
            logger.warning(f"⚠️ Could not parse base path, defaulting to /api: {e}")

        # Return mock URL
        mock_url = f"http://localhost:{SIMULATOR_PORT}{base_path}"
        logger.info(f"🌐 Mock available at {mock_url}")
        return mock_url

if __name__ == "__main__":
    # Test
    print("Testing ApiSandboxTool...")
    tool = ApiSandboxTool()

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
