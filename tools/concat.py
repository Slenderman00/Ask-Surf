from tool_executor import ToolResult

TOOL_NAME   = "concat"
DESCRIPTION = "Concatenate multiple strings into a single string"

PARAMETERS = {
    "type": "object",
    "properties": {
        "parts": {
            "type": "array",
            "description": "List of strings or pipe results to join together in order",
            "items": {"type": "string"},
            "pipeable": False,
        },
        "separator": {
            "type": "string",
            "description": "String inserted between each part",
            "pipeable": False,
        },
    },
    "required": ["parts"],
}

def execute(arguments, context):
    parts = arguments.get("parts", [])
    separator = arguments.get("separator", "")
    executor = context.get("executor")
    cwd = context.get("cwd", "")

    if not isinstance(parts, list):
        return ToolResult(value="Error: parts must be a list", result_type="error")

    resolved = []
    trace = []

    try:
        for part in parts:
            if isinstance(part, dict) and "pipe" in part:
                resolved_part = executor.resolve(part, cwd, trace)
                resolved.append(str(resolved_part))
            else:
                resolved.append(str(part))

        return ToolResult(
            value=str(separator).join(resolved),
            result_type="text"
        )
    except Exception as e:
        return ToolResult(value=f"Error: {e}", result_type="error")
