"""
Patch Tools (Search and Replace).
"""
import os
try:
    from tools.files import read_file, write_file
except ImportError:
    from agents.tools.files import read_file, write_file

def patch_file(path: str, search_content: str, replace_content: str) -> str:
    """Apply a patch to a file by replacing the first occurrence of search_content."""
    content = read_file(path)
    if content.startswith("Error"):
        return content

    # Simple Python replace
    if search_content not in content:
        return f"Patch failed: search_content not found in '{path}'."

    new_content = content.replace(search_content, replace_content, 1)

    result = write_file(path, new_content)
    if result.startswith("Error"):
        return result
    return f"Successfully patched '{path}'."
