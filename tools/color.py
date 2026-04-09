from tool_executor import ToolResult


TOOL_NAME   = "color"
DESCRIPTION = "Wrap text in an ANSI color"

ANSI_COLORS = {
    "red":     "\033[31m",
    "green":   "\033[32m",
    "yellow":  "\033[33m",
    "blue":    "\033[34m",
    "magenta": "\033[35m",
    "cyan":    "\033[36m",
    "white":   "\033[37m",
}

PARAMETERS = {
    "type": "object",
    "properties": {
        "data": {
            "type":        "string",
            "description": "The text to colorize",
            "pipeable":    True,
        },
        "color": {
            "type":        "string",
            "description": "Color name: red, green, yellow, blue, magenta, cyan, white",
            "pipeable":    False,
        },
    },
    "required": ["data", "color"],
}


def execute(arguments, context):
    data  = arguments.get("data") or arguments.get("text", "")
    color = arguments.get("color", "").lower()
    code  = ANSI_COLORS.get(color, "")

    if not code:
        return ToolResult(value=data, result_type="text")

    return ToolResult(value=f"{code}{data}\033[0m", result_type="text")
