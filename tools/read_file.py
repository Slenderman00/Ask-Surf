try:
    from tool_executor import ToolResult
except ImportError:
    from .tool_executor import ToolResult
from pathlib import Path


TOOL_NAME   = "read_file"
DESCRIPTION = "Read a file from disk and return its contents as bytes"

PARAMETERS = {
    "type": "object",
    "properties": {
        "path": {
            "type":        "string",
            "description": "Path to the file to read",
            "pipeable":    False,
        }
    },
    "required": ["path"],
}


def execute(arguments, context):
    path = Path(arguments.get("path", ""))
    if not path.is_absolute():
        path = Path(context.get("cwd", ".")) / path

    try:
        data = path.read_bytes()
        return ToolResult(value=data, result_type="bytes", display=f"read {len(data)} bytes from {path}")
    except Exception as e:
        return ToolResult(value=f"Error: could not read {path} — {e}", result_type="error")
