try:
    from tool_executor import ToolResult
except ImportError:
    from .tool_executor import ToolResult
import urllib.request
import urllib.parse
import json


TOOL_NAME   = "search"
DESCRIPTION = "Search the web using the local SearXNG instance and return results as text"

PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {
            "type":        "string",
            "description": "The search query",
            "pipeable":    False,
        },
        "num_results": {
            "type":        "integer",
            "description": "Number of results to return (default 5)",
            "pipeable":    False,
        },
    },
    "required": ["query"],
}


def execute(arguments, context):
    query       = arguments.get("query", "")
    num_results = arguments.get("num_results", 5)
    config      = context.get("tool_config", {})
    base_url    = config.get("base_url", "http://127.0.0.1:8888")

    params = urllib.parse.urlencode({
        "q":       query,
        "format":  "json",
        "engines": config.get("engines", ""),
    })

    url = f"{base_url}/search?{params}"

    try:
        req  = urllib.request.Request(url, headers={"User-Agent": "surf/3.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        results = data.get("results", [])[:num_results]

        if not results:
            return ToolResult(value="No results found.", result_type="text")

        lines = []
        for i, r in enumerate(results, 1):
            title   = r.get("title", "")
            url_r   = r.get("url", "")
            content = r.get("content", "")
            lines.append(f"{i}. {title}\n   {url_r}\n   {content}\n")

        return ToolResult(
            value="\n".join(lines),
            result_type="text",
            display=f"search: {query} ({len(results)} results)"
        )

    except Exception as e:
        return ToolResult(value=f"Error: search failed — {e}", result_type="error")
