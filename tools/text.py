try:
    from tool_executor import ToolResult
except ImportError:
    from .tool_executor import ToolResult


TOOL_NAME   = "text"
DESCRIPTION = "Inject a literal string into a pipe"

PARAMETERS = {
    "type": "object",
    "properties": {
        "content": {
            "type":        "string",
            "description": "The text to inject",
            "pipeable":    False,
        }
    },
    "required": ["content"],
}


def execute(arguments, context):
    # accept content, text, or data as the argument name
    value = (
        arguments.get("content")
        or arguments.get("text")
        or arguments.get("data")
        or ""
    )
    return ToolResult(value=value, result_type="text")
