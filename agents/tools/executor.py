"""
Executor Tool - Runs shell commands in a subprocess.
Used by CoderAgent for self-correction and testing.
"""
import subprocess
import shlex
from typing import Tuple, Optional

def run_command(command: str, timeout: int = 30) -> Tuple[int, str, str]:
    """
    Executes a shell command and returns the exit code, stdout, and stderr.

    Args:
        command (str): The command to execute.
        timeout (int): Maximum time in seconds to wait for completion.

    Returns:
        Tuple[int, str, str]: (return_code, stdout, stderr)
    """
    try:
        # Split command for safety if not using shell=True, but for flexible testing we might need shell=True
        # or careful parsing. Since the agent generates full commands (e.g. "pytest tests/"),
        # we'll use shell=True for now to support pipes/redirects if needed,
        # acknowledging the security implications in a real environment.
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", f"Execution failed: {str(e)}"
