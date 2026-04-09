from tool_executor import ToolResult


TOOL_NAME   = "underline"
DESCRIPTION = "Wrap text in ANSI underline"

PARAMETERS = {
    "type": "object",
    "properties": {
        "data": {
            "type":        "string",
            "description": "The text to underline",
            "pipeable":    True,
        }
    },
    "required": ["data"],
}


def execute(arguments, context):
    data = arguments.get("data", "")
    return ToolResult(value=f"\033[4m{data}\033[0m", result_type="text")
