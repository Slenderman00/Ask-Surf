try:
    from tool_executor import ToolResult
except ImportError:
    from .tool_executor import ToolResult
from pathlib import Path


TOOL_NAME   = "save_file"
DESCRIPTION = "Save data to a file in the current working directory, then pass the data through unchanged"

PARAMETERS = {
    "type": "object",
    "properties": {
        "filename": {
            "type":        "string",
            "description": "The filename to save to",
            "pipeable":    False,
        },
        "data": {
            "type":        "string",
            "description": "The data to save",
            "pipeable":    True,
        },
    },
    "required": ["filename", "data"],
}


def execute(arguments, context):
    filename = arguments.get("filename", "output.txt")
    data     = arguments.get("data", "")
    cwd      = context.get("cwd", ".")
    path     = Path(cwd) / filename

    try:
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(str(data))
        return ToolResult(value=data, result_type="bytes" if isinstance(data, bytes) else "text", display=f"saved to {path}")
    except Exception as e:
        return ToolResult(value=f"Error: could not save {path} — {e}", result_type="error")
