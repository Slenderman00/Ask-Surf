from tool_executor import ToolResult


TOOL_NAME   = "to_model"
DESCRIPTION = "Return the piped data back to the model as visible text for reasoning"

PARAMETERS = {
    "type": "object",
    "properties": {
        "data": {
            "type":        "string",
            "description": "The data to make visible to the model",
            "pipeable":    True,
        }
    },
    "required": ["data"],
}


def execute(arguments, context):
    data = arguments.get("data", "")

    # if bytes, decode best effort so the model can read it
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            data = data.decode("latin-1", errors="replace")

    return ToolResult(
        value=str(data),
        result_type="text",
        display=str(data),
    )
