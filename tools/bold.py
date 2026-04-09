from tool_executor import ToolResult


TOOL_NAME   = "bold"
DESCRIPTION = "Wrap text in ANSI bold"

PARAMETERS = {
    "type": "object",
    "properties": {
        "data": {
            "type":        "string",
            "description": "The text to make bold",
            "pipeable":    True,
        }
    },
    "required": ["data"],
}


def execute(arguments, context):
    data = arguments.get("data", "")
    return ToolResult(value=f"\033[1m{data}\033[0m", result_type="text")
