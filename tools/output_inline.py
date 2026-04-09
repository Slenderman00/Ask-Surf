try:
    from tool_executor import ToolResult, PipeError
except ImportError:
    from .tool_executor import ToolResult, PipeError
except ImportError:
    from .tool_executor import ToolResult, PipeError
import uuid


TOOL_NAME   = "output_inline"
DESCRIPTION = "Replace this tool call location in the response text with the piped output"

PARAMETERS = {
    "type": "object",
    "properties": {
        "data": {
            "type":        "string",
            "description": "The content to render inline",
            "pipeable":    True,
        }
    },
    "required": ["data"],
}


def execute(arguments, context):
    data = arguments.get("data") or arguments.get("text") or arguments.get("content", "")
    if not isinstance(data, str):
        data = str(data)

    executor = context.get("executor")
    if executor:
        marker = f"__INLINE_{uuid.uuid4().hex}__"
        executor.register_inline(marker, data)
        # summary is the data itself so it goes back to the model correctly
        return ToolResult(value=marker, result_type="text", display=data)

    # no executor — just return the data directly
    return ToolResult(value=data, result_type="text", display=data)
