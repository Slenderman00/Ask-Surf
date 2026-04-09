try:
    from tool_executor import ToolResult
except ImportError:
    from .tool_executor import ToolResult
import subprocess


TOOL_NAME   = "nmap"
DESCRIPTION = "Run an nmap scan against a target. Shows the command and asks for confirmation before running."

PARAMETERS = {
    "type": "object",
    "properties": {
        "target": {
            "type":        "string",
            "description": "The target host or IP to scan",
            "pipeable":    False,
        },
        "flags": {
            "type":        "string",
            "description": "nmap flags to use, e.g. -sV -p 80,443",
            "pipeable":    False,
        },
    },
    "required": ["target"],
}


def execute(arguments, context):
    target  = arguments.get("target", "")
    config  = context.get("tool_config", {})
    flags   = arguments.get("flags", config.get("default_flags", "-sV"))
    prompt  = context.get("prompt")

    command = f"nmap {flags} {target}"

    if config.get("require_confirm", True) and prompt:
        confirmed = prompt(f"About to run:\n  {command}\nProceed?", prompt_type="confirm")
        if confirmed in (False, "false", "False", "no", "n"):
            return ToolResult(value="Scan cancelled.", result_type="text")

    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout or result.stderr or "No output."
        return ToolResult(value=output, result_type="text", display=f"nmap {target}")
    except subprocess.TimeoutExpired:
        return ToolResult(value="Error: nmap timed out after 120 seconds", result_type="error")
    except Exception as e:
        return ToolResult(value=f"Error: {e}", result_type="error")
