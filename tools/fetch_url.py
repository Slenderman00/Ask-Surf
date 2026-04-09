try:
    from tool_executor import ToolResult
except ImportError:
    from .tool_executor import ToolResult
import urllib.request
import urllib.error
import re


TOOL_NAME   = "fetch_url"
DESCRIPTION = "Fetch the contents of a URL and return as text. HTML is automatically stripped to readable text."

PARAMETERS = {
    "type": "object",
    "properties": {
        "url": {
            "type":        "string",
            "description": "The URL to fetch",
            "pipeable":    False,
        },
        "raw": {
            "type":        "boolean",
            "description": "If true, return raw bytes instead of stripped text",
            "pipeable":    False,
        },
    },
    "required": ["url"],
}


def strip_html(html_bytes):
    """strip html tags and collapse whitespace to get readable text"""
    try:
        text = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        return html_bytes.decode("latin-1", errors="replace")

    # remove scripts and styles entirely
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>",   " ", text, flags=re.DOTALL | re.IGNORECASE)
    # strip remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # decode common html entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#39;", "'")
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # truncate to 4000 chars so it fits in context
    if len(text) > 4000:
        text = text[:4000] + "... [truncated]"
    return text


def execute(arguments, context):
    url     = arguments.get("url", "")
    raw     = arguments.get("raw", False)
    config  = context.get("tool_config", {})
    timeout = config.get("timeout", 30)

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": config.get("user_agent", "surf/3.0"),
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()

        if raw:
            return ToolResult(value=data, result_type="bytes", display=f"fetched {len(data)} bytes from {url}")

        text = strip_html(data)
        return ToolResult(value=text, result_type="text", display=f"fetched {url}")

    except Exception as e:
        return ToolResult(value=f"Error: failed to fetch {url} — {e}", result_type="error")
