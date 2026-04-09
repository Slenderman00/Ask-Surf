try:
    from tool_executor import ToolResult
except ImportError:
    from .tool_executor import ToolResult


TOOL_NAME   = "ask_user"
DESCRIPTION = "Suspend execution and ask the user a question, returning their answer"

PARAMETERS = {
    "type": "object",
    "properties": {
        "question": {
            "type":        "string",
            "description": "The question to ask the user",
            "pipeable":    False,
        },
        "type": {
            "type":        "string",
            "description": "Prompt type: text, confirm, or choice",
            "pipeable":    False,
        },
        "choices": {
            "type":        "array",
            "description": "List of choices for type=choice",
            "items":       {"type": "string"},
            "pipeable":    False,
        },
    },
    "required": ["question"],
}


def execute(arguments, context):
    question    = arguments.get("question", "")
    prompt_type = arguments.get("type", "text")
    choices     = arguments.get("choices", [])
    prompt_fn   = context.get("prompt")

    if not prompt_fn:
        return ToolResult(value="Error: no prompt function available", result_type="error")

    try:
        answer = prompt_fn(question, prompt_type=prompt_type, choices=choices)
        return ToolResult(value=str(answer), result_type="text", display=f"user answered: {answer}")
    except Exception as e:
        return ToolResult(value=f"Error: prompt failed — {e}", result_type="error")
