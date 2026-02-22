import shutil
import subprocess
import time
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"


class TestContainerPackagingContract(unittest.TestCase):
    def test_dockerfile_uses_sdk_python_copy_paths(self) -> None:
        content = DOCKERFILE_PATH.read_text(encoding="utf-8")
        self.assertIn("COPY sdk/python/lib ./sdk/python/lib", content)
        self.assertIn("COPY sdk/python/agents ./sdk/python/agents", content)
        self.assertIn("CMD [\"python\", \"-m\", \"gateway_runtime\"]", content)

    def test_gateway_startup_script_imports_real_module(self) -> None:
        startup_script = (REPO_ROOT / "scripts" / "start_gateway.py").read_text(encoding="utf-8")
        self.assertIn("from gateway_runtime import app", startup_script)


@unittest.skipUnless(shutil.which("docker"), "docker binary is required for smoke test")
class TestGatewayContainerSmoke(unittest.TestCase):
    def test_container_serves_status_and_game_state(self) -> None:
        image_tag = "agent-swarm-gateway-smoke:test"
        container_name = f"agent-swarm-gateway-smoke-{int(time.time())}"

        build_cmd = ["docker", "build", "-t", image_tag, "."]
        run_cmd = [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            container_name,
            "-p",
            "18789:18789",
            image_tag,
        ]

        subprocess.run(build_cmd, cwd=REPO_ROOT, check=True)
        subprocess.run(run_cmd, cwd=REPO_ROOT, check=True)

        try:
            self._wait_for_status("http://127.0.0.1:18789/status")
            self._assert_json_endpoint("http://127.0.0.1:18789/status")
            self._assert_json_endpoint("http://127.0.0.1:18789/api/v1/game-state")
        finally:
            subprocess.run(["docker", "stop", container_name], cwd=REPO_ROOT, check=False)

    def _wait_for_status(self, url: str) -> None:
        for _ in range(30):
            try:
                with urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        return
            except URLError:
                time.sleep(1)
        self.fail(f"gateway endpoint never became healthy: {url}")

    def _assert_json_endpoint(self, url: str) -> None:
        with urlopen(url, timeout=5) as response:
            self.assertEqual(response.status, 200)
            body = response.read().decode("utf-8")
            self.assertTrue(body.startswith("{") or body.startswith("["))


if __name__ == "__main__":
    unittest.main()
