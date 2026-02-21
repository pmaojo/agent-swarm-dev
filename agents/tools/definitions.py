"""
Tool Definitions for CoderAgent (OpenAI Tool Calling Format).
"""

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file from the file system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to read (relative to repo root)."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Overwrites existing files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to write."
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content to write to the file."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Apply a partial edit to a file using search and replace. Replaces the first occurrence of `search_content` with `replace_content`. Use this for large files to avoid overwriting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to patch."
                    },
                    "search_content": {
                        "type": "string",
                        "description": "The exact string to search for in the file."
                    },
                    "replace_content": {
                        "type": "string",
                        "description": "The new string to replace the search content with."
                    }
                },
                "required": ["path", "search_content", "replace_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories in a given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list. Defaults to current directory."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_logs",
            "description": "Read the last N lines of a log file or search for specific patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the log file."
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to read from the end (default: 50)."
                    },
                    "grep": {
                        "type": "string",
                        "description": "Optional search pattern (grep)."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command. Restricted commands require approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute."
                    },
                    "reason": {
                        "type": "string",
                        "description": "The reason for executing this command."
                    }
                },
                "required": ["command", "reason"]
            }
        }
    }
]
