try:
    from tool_executor import ToolResult
except ImportError:
    from .tool_executor import ToolResult


TOOL_NAME   = "create_table"
DESCRIPTION = "Render a unicode table from headers and rows"

PARAMETERS = {
    "type": "object",
    "properties": {
        "headers": {
            "type":        "array",
            "description": "List of column header strings",
            "items":       {"type": "string"},
            "pipeable":    False,
        },
        "rows": {
            "type":        "array",
            "description": "List of rows, each row is a list of cell values",
            "items":       {"type": "array"},
            "pipeable":    False,
        },
    },
    "required": ["headers", "rows"],
}


def execute(arguments, context):
    headers = arguments.get("headers", [])
    rows    = arguments.get("rows", [])
    config  = context.get("tool_config", {})
    style   = config.get("style", "unicode")

    if not headers:
        return ToolResult(value="Error: no headers provided", result_type="error")

    # convert all cells to strings
    headers = [str(h) for h in headers]
    rows    = [[str(c) for c in row] for row in rows]

    # calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))

    if style == "ascii":
        h_line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        h_row  = "|" + "|".join(f" {h:<{w}} " for h, w in zip(headers, widths)) + "|"
        lines  = [h_line, h_row, h_line]
        for row in rows:
            padded = row + [""] * (len(widths) - len(row))
            lines.append("|" + "|".join(f" {c:<{w}} " for c, w in zip(padded, widths)) + "|")
        lines.append(h_line)
    elif style == "markdown":
        h_row  = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, widths)) + " |"
        sep    = "| " + " | ".join("-" * w for w in widths) + " |"
        lines  = [h_row, sep]
        for row in rows:
            padded = row + [""] * (len(widths) - len(row))
            lines.append("| " + " | ".join(f"{c:<{w}}" for c, w in zip(padded, widths)) + " |")
    else:
        # unicode
        top  = "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"
        mid  = "├" + "┼".join("─" * (w + 2) for w in widths) + "┤"
        bot  = "└" + "┴".join("─" * (w + 2) for w in widths) + "┘"
        h_row = "│" + "│".join(f" {h:<{w}} " for h, w in zip(headers, widths)) + "│"
        lines = [top, h_row, mid]
        for row in rows:
            padded = row + [""] * (len(widths) - len(row))
            lines.append("│" + "│".join(f" {c:<{w}} " for c, w in zip(padded, widths)) + "│")
        lines.append(bot)

    return ToolResult(value="\n".join(lines), result_type="text")
