"""
Executor Tool - Runs shell commands in a subprocess.
Used by CoderAgent for self-correction and testing.
Delegates to `agents.tools.shell.execute_command` for NIST Guardrails.
"""
from typing import Tuple
from agents.tools.shell import execute_command

def run_command(command: str, timeout: int = 30) -> Tuple[int, str, str]:
    """
    Executes a shell command via CommandGuard and returns the exit code, stdout, and stderr.

    Args:
        command (str): The command to execute.
        timeout (int): Ignored by CommandGuard (defaults to 120s), kept for API compatibility.

    Returns:
        Tuple[int, str, str]: (return_code, stdout, stderr)
    """
    try:
        # execute_command returns a dict: {'status', 'stdout', 'stderr', 'returncode', 'error', 'uuid', 'message'}
        result = execute_command(command, reason="Executor Tool (Coder/Test)")

        if result.get("status") == "success":
            return result.get("returncode", 0), result.get("stdout", ""), result.get("stderr", "")

        elif result.get("status") == "failure":
            return -1, "", result.get("error", "Unknown failure")

        elif result.get("status") == "pending_approval":
            return -2, "", f"Command requires approval. UUID: {result.get('uuid')}. Message: {result.get('message')}"

        else:
            return -1, "", "Unknown status from CommandGuard"

    except Exception as e:
        return -1, "", f"Execution failed: {str(e)}"
