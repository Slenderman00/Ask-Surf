from tool_executor import ToolResult
from tool_executor import ToolResult, PipeError


TOOL_NAME   = "tee"
DESCRIPTION = "Fan out data to multiple tools as side effects and return the data unchanged"

PARAMETERS = {
    "type": "object",
    "properties": {
        "data": {
            "type":        "string",
            "description": "The data to pass through and fan out",
            "pipeable":    True,
        },
        "pipes": {
            "type":        "array",
            "description": (
                "List of pipe definitions to execute as side effects. "
                "Each entry is a pipe object with 'pipe' and 'arguments'. "
                "The tee data is automatically injected into the first pipeable argument."
            ),
            "items": {
                "type": "object",
            },
            "pipeable": False,
        },
    },
    "required": ["data", "pipes"],
}


def execute(arguments, context):
    data     = arguments.get("data")
    pipes    = arguments.get("pipes", [])
    executor = context.get("executor")
    cwd      = context.get("cwd", "")

    if data is None:
        return ToolResult(
            value="Error: tee received no data",
            result_type="error"
        )

    branch_summaries = []

    for pipe_def in pipes:
        if not isinstance(pipe_def, dict) or "pipe" not in pipe_def:
            branch_summaries.append("skipped: invalid pipe definition")
            continue

        tool_name = pipe_def["pipe"]
        branch_args = dict(pipe_def.get("arguments", {}))

        # inject data into the first pipeable argument of the branch tool
        # so bytes flow through naturally without needing re-resolution
        branch_args = _inject_data(branch_args, data, tool_name, executor)

        trace = []
        try:
            result = executor.run_tool(tool_name, branch_args, cwd)
            if result.type == "error":
                branch_summaries.append(f"{tool_name}: {result.value}")
            else:
                branch_summaries.append(f"{tool_name}: ok")
        except Exception as e:
            branch_summaries.append(f"{tool_name}: error — {e}")

    summary = "tee → " + ", ".join(branch_summaries)

    return ToolResult(value=data, result_type=_infer_type(data), display=summary)


def _inject_data(branch_args, data, tool_name, executor):
    """inject tee data into the first pipeable argument of the branch tool"""
    module = executor.tools.get(tool_name)
    if module is None:
        return branch_args

    params     = getattr(module, "PARAMETERS", {})
    properties = params.get("properties", {})

    for arg_name, arg_def in properties.items():
        if arg_def.get("pipeable", False) and arg_name not in branch_args:
            branch_args[arg_name] = data
            break

    return branch_args


def _infer_type(data):
    if isinstance(data, bytes):
        return "bytes"
    return "text"


TOOL_NAME   = "tee"
DESCRIPTION = "Fan out data to multiple tools as side effects and return the data unchanged"

PARAMETERS = {
    "type": "object",
    "properties": {
        "data": {
            "type":        "string",
            "description": "The data to pass through and fan out",
            "pipeable":    True,
        },
        "pipes": {
            "type":        "array",
            "description": (
                "List of pipe definitions to execute as side effects. "
                "Each entry is a pipe object with 'pipe' and 'arguments'. "
                "The tee data is automatically injected into the first pipeable argument."
            ),
            "items": {
                "type": "object",
            },
            "pipeable": False,
        },
    },
    "required": ["data", "pipes"],
}


def execute(arguments, context):
    data     = arguments.get("data")
    pipes    = arguments.get("pipes", [])
    executor = context.get("executor")
    cwd      = context.get("cwd", "")

    if data is None:
        return ToolResult(
            value="Error: tee received no data",
            result_type="error"
        )

    branch_summaries = []

    for pipe_def in pipes:
        if not isinstance(pipe_def, dict) or "pipe" not in pipe_def:
            branch_summaries.append("skipped: invalid pipe definition")
            continue

        tool_name = pipe_def["pipe"]
        branch_args = dict(pipe_def.get("arguments", {}))

        branch_args = _inject_data(branch_args, data, tool_name, executor)

        trace = []
        try:
            resolved_branch_args = {
                k: executor.resolve(v, cwd, trace) for k, v in branch_args.items()
            }
            result = executor.run_tool(tool_name, resolved_branch_args, cwd)
            if result.type == "error":
                branch_summaries.append(f"{tool_name}: {result.value}")
            else:
                branch_summaries.append(f"{tool_name}: ok")
        except Exception as e:
            branch_summaries.append(f"{tool_name}: error — {e}")

    summary = "tee → " + ", ".join(branch_summaries)

    return ToolResult(value=data, result_type=_infer_type(data), display=summary)


def _inject_data(branch_args, data, tool_name, executor):
    module = executor.tools.get(tool_name)
    if module is None:
        return branch_args

    params     = getattr(module, "PARAMETERS", {})
    properties = params.get("properties", {})

    for arg_name, arg_def in properties.items():
        if arg_def.get("pipeable", False) and arg_name not in branch_args:
            branch_args[arg_name] = data
            break

    return branch_args


def _infer_type(data):
    if isinstance(data, bytes):
        return "bytes"
    return "text"
