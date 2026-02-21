import unittest
from agents.tools.executor import run_command
import sys
import os

# Add parent dir to path for import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestExecutor(unittest.TestCase):

    def test_run_command_success(self):
        code, stdout, stderr = run_command("echo hello")
        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip(), "hello")

    def test_run_command_failure(self):
        code, stdout, stderr = run_command("false")
        self.assertNotEqual(code, 0)

    def test_run_command_timeout(self):
        code, stdout, stderr = run_command("sleep 5", timeout=1)
        self.assertEqual(code, -1)
        self.assertIn("timed out", stderr)

    def test_python_script_execution(self):
        # Use single quotes inside double quotes for the shell command
        cmd = "python3 -c \"print('test_py')\""
        code, stdout, stderr = run_command(cmd)
        if code != 0:
            print(f"Command failed: {cmd}\nStdout: {stdout}\nStderr: {stderr}")
        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip(), "test_py")

if __name__ == '__main__':
    unittest.main()
