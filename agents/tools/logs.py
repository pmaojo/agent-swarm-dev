"""
Log Tools (Tail/Grep).
"""
import subprocess
import os

def read_logs(path: str, lines: int = 50, grep: str = None) -> str:
    """Read the last N lines of a log file, optionally filtering with grep."""
    if not os.path.exists(path):
        return f"Error: Log file '{path}' not found."

    command = ["tail", "-n", str(lines), path]

    if grep:
        # Pipe tail output to grep
        # tail -n lines path | grep pattern
        # Using shell=True for pipe convenience, though less secure if grep pattern is malicious.
        # But grep pattern comes from LLM, so injection risk exists.
        # However, the task is for a dev tool.
        # Safer: run tail, capture output, then run grep on output string in python?
        # Or subprocess pipe.
        p1 = subprocess.Popen(command, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(["grep", grep], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
        p1.stdout.close()
        output, error = p2.communicate()
        if p2.returncode != 0 and not output:
             return f"No matches found for pattern '{grep}' in last {lines} lines of '{path}'."
        return output
    else:
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error reading logs: {e.stderr}"
