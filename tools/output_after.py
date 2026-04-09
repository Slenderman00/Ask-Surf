from tool_executor import ToolResult


TOOL_NAME   = "output_after"
DESCRIPTION = "Append the piped output after the full response text"

PARAMETERS = {
    "type": "object",
    "properties": {
        "data": {
            "type":        "string",
            "description": "The content to append after the response",
            "pipeable":    True,
        }
    },
    "required": ["data"],
}


def execute(arguments, context):
    data = arguments.get("data", "")
    if not isinstance(data, str):
        data = str(data)

    executor = context.get("executor")
    if executor:
        executor.register_after(data)

    return ToolResult(value=data, result_type="text", display=data)
