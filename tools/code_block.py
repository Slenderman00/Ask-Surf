from tool_executor import ToolResult
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import TerminalFormatter
from pygments.util import ClassNotFound


TOOL_NAME   = "code_block"
DESCRIPTION = "Render a syntax highlighted code block string"

PARAMETERS = {
    "type": "object",
    "properties": {
        "code": {
            "type":        "string",
            "description": "The code to highlight",
            "pipeable":    True,
        },
        "language": {
            "type":        "string",
            "description": "The programming language for syntax highlighting",
            "pipeable":    False,
        },
    },
    "required": ["code"],
}


def execute(arguments, context):
    code     = arguments.get("code", "")
    language = arguments.get("language", "")

    try:
        lexer     = get_lexer_by_name(language)
        formatted = highlight(code, lexer, TerminalFormatter())
    except ClassNotFound:
        # no lexer found, just wrap in cyan
        formatted = f"\033[36m{code}\033[0m"

    return ToolResult(value=formatted, result_type="text")
