import os
import json
import importlib.util
from pathlib import Path


TOOLS_DIR = Path(__file__).parent.parent / "tools"


class ToolResult:
    def __init__(self, value, result_type="text", display=None):
        self.value       = value
        self.type        = result_type
        self.display     = display
        self.summary     = display if display else (
            value if isinstance(value, str) else f"<{result_type} {len(value)} bytes>"
        )


class ToolExecutor:
    def __init__(self, tools_config, prompt_fn):
        self.tools_config = tools_config
        self.prompt_fn    = prompt_fn
        self.tools        = {}
        self.load_tools()

    def load_tools(self):
        """scan the tools directory and load all enabled tools"""
        if not TOOLS_DIR.exists():
            return

        for tool_file in sorted(TOOLS_DIR.glob("*.py")):
            tool_name = tool_file.stem

            config = self.tools_config.get(tool_name, {})
            if not config.get("enabled", False):
                continue

            spec   = importlib.util.spec_from_file_location(tool_name, tool_file)
            module = importlib.util.module_from_spec(spec)

            try:
                spec.loader.exec_module(module)
            except Exception as e:
                print(f"Failed to load tool {tool_name}: {e}")
                continue

            self.tools[tool_name] = module
            print(f"Loaded tool: {tool_name}")

    def get_tools_schema(self):
        """build the tools list to pass to create_chat_completion"""
        schema = []
        for name, module in self.tools.items():
            raw_params = getattr(module, "PARAMETERS", {"type": "object", "properties": {}})
            params     = self._strip_pipeable(raw_params)
            schema.append({
                "type": "function",
                "function": {
                    "name":        getattr(module, "TOOL_NAME", name),
                    "description": getattr(module, "DESCRIPTION", ""),
                    "parameters":  params,
                }
            })
        return schema

    def _strip_pipeable(self, params):
        """remove the pipeable key from parameter definitions before sending to the model"""
        import copy
        params = copy.deepcopy(params)
        for prop in params.get("properties", {}).values():
            prop.pop("pipeable", None)
        return params

    def build_context(self, cwd, tool_name):
        """build the context dict passed to every tool execute() call"""
        return {
            "cwd":         cwd,
            "settings":    self._load_settings(),
            "tool_config": self.tools_config.get(tool_name, {}),
            "prompt":      self.prompt_fn,
            "executor":    self,
        }

    def _load_settings(self):
        try:
            from settings import load_settings
        except ImportError:
            from .settings import load_settings
        return load_settings()

    def resolve(self, value, cwd, trace):
        """depth-first recursive pipe resolver"""
        if not isinstance(value, dict) or "pipe" not in value:
            return value

        tool_name = value["pipe"]
        raw_args  = value.get("arguments", {})

        # resolve all arguments first before executing
        resolved_args = {k: self.resolve(v, cwd, trace) for k, v in raw_args.items()}

        result = self.run_tool(tool_name, resolved_args, cwd)

        trace.append({
            "tool":   tool_name,
            "args":   resolved_args,
            "result": result.summary,
            "type":   result.type,
        })

        # abort chain on error
        if result.type == "error":
            raise PipeError(result.value, tool_name)

        return result.value

    def run_tool(self, tool_name, arguments, cwd):
        """execute a single tool by name with already-resolved arguments"""
        print(f"run_tool called: {tool_name} args={list(arguments.keys())}", flush=True)
        module = self.tools.get(tool_name)
        if module is None:
            print(f"run_tool: tool {tool_name} not found", flush=True)
            return ToolResult(
                value=f"Error: tool '{tool_name}' not found or not enabled",
                result_type="error"
            )

        context = self.build_context(cwd, tool_name)

        try:
            result = module.execute(arguments, context)
            print(f"run_tool {tool_name} returned: {repr(result.value)[:50]}", flush=True)
            return result
        except PipeError:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            return ToolResult(
                value=f"Error: tool '{tool_name}' raised an exception: {e}",
                result_type="error"
            )

    def execute(self, tool_call, cwd):
        """
        top-level entry point called by the service for each tool call
        the model emits. resolves pipes, runs the tool, records trace.
        returns a ToolResult.
        """
        trace     = []
        fn        = tool_call.get("function", {})
        tool_name = fn.get("name", "")

        try:
            raw_args = json.loads(fn.get("arguments", "{}"))
        except json.JSONDecodeError:
            return ToolResult(
                value=f"Error: could not parse arguments for '{tool_name}'",
                result_type="error"
            )

        # resolve any pipes in arguments
        try:
            resolved_args = {k: self.resolve(v, cwd, trace) for k, v in raw_args.items()}
        except PipeError as e:
            return ToolResult(
                value=str(e),
                result_type="error",
                display=self._format_trace(trace)
            )

        result = self.run_tool(tool_name, resolved_args, cwd)

        # attach trace to result for verbose/trace output
        result.trace = trace

        return result

    def render(self, response):
        """
        post-process the model's final response text.
        replaces output_inline markers with their rendered content
        and appends output_after content at the end.
        """
        # the tool executor stores pending inline and after outputs
        # during execution so we can splice them in here
        inline_outputs = getattr(self, "_inline_outputs", {})
        after_outputs  = getattr(self, "_after_outputs", [])

        for marker, content in inline_outputs.items():
            response = response.replace(marker, content)

        if after_outputs:
            response = response + "\n" + "\n".join(after_outputs)

        # clear for next turn
        self._inline_outputs = {}
        self._after_outputs  = []

        return response

    def register_inline(self, marker, content):
        if not hasattr(self, "_inline_outputs"):
            self._inline_outputs = {}
        self._inline_outputs[marker] = content

    def register_after(self, content):
        if not hasattr(self, "_after_outputs"):
            self._after_outputs = []
        self._after_outputs.append(content)

    def _format_trace(self, trace):
        if not trace:
            return None
        lines = []
        for step in trace:
            lines.append(f"[Tool: {step['tool']}] → {step['result']}")
        return "\n".join(lines)


class PipeError(Exception):
    """raised when a pipe step fails, carrying the error message up the chain"""
    def __init__(self, message, tool_name):
        self.tool_name = tool_name
        super().__init__(f"Error in pipe at '{tool_name}': {message}")
