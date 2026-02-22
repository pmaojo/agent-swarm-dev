"""
File System Tools.
"""
import os
import shutil

def read_file(path: str) -> str:
    """Read the content of a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File '{path}' not found."
    except Exception as e:
        return f"Error reading file '{path}': {e}"

def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to '{path}'."
    except Exception as e:
        return f"Error writing file '{path}': {e}"

def list_dir(path: str = ".") -> str:
    """List contents of a directory."""
    try:
        files = os.listdir(path)
        output = f"Listing for '{path}':\n"
        for f in files:
            full_path = os.path.join(path, f)
            if os.path.isdir(full_path):
                output += f"{f}/\n"
            else:
                output += f"{f}\n"
        return output
    except Exception as e:
        return f"Error listing directory '{path}': {e}"
