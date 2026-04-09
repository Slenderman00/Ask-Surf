try:
    from tool_executor import ToolResult
except ImportError:
    from .tool_executor import ToolResult
import tempfile
import os


TOOL_NAME   = "image_to_cli"
DESCRIPTION = "Render image bytes as unicode art for display in the terminal"

PARAMETERS = {
    "type": "object",
    "properties": {
        "data": {
            "type":        "string",
            "description": "Raw image bytes to render",
            "pipeable":    True,
        }
    },
    "required": ["data"],
}


def execute(arguments, context):
    import climage
    import shutil

    data   = arguments.get("data", b"")
    config = context.get("tool_config", {})
    width  = config.get("width", shutil.get_terminal_size().columns)

    if not isinstance(data, bytes):
        return ToolResult(value="Error: image_to_cli requires bytes input", result_type="error")

    try:
        # write to temp file since climage needs a path
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        result = climage.convert(tmp_path, is_unicode=True, width=width)
        os.unlink(tmp_path)
        return ToolResult(value=result, result_type="text", display=f"[image {len(data)} bytes]")
    except Exception as e:
        return ToolResult(value=f"Error: could not render image — {e}", result_type="error")
