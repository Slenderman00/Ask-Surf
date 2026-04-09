from llama_cpp import Llama
from fastapi import FastAPI, Response
from pydantic import BaseModel

try:
    from settings import load_settings, load_tools, get_model_path
except ImportError:
    from .settings import load_settings, load_tools, get_model_path

try:
    from tool_executor import ToolExecutor
except ImportError:
    from .tool_executor import ToolExecutor

try:
    from utility import parse_message, strip_think
except ImportError:
    from .utility import parse_message, strip_think

import uvicorn
import asyncio
import concurrent.futures
import threading
import time
import os
import json
import re


SOCKET_PATH = "/tmp/surf.sock"

TERMINAL_TOOLS = {"output_inline", "output_after"}
REASONING_TOOLS = {"to_model", "ask_user"}
WRAPPABLE_TOP_LEVEL_TOOLS = {"bold", "color", "underline", "code_block", "tee", "text", "concat"}


class QuestionRequest(BaseModel):
    question: str
    cwd: str
    verbose: bool = False
    trace: bool = False


class PromptAnswer(BaseModel):
    answer: str


class SurfService:
    def __init__(self):
        self.llm            = None
        self.cwd            = ""
        self.messages       = []
        self.api_server     = FastAPI()
        self.last_activity  = time.time()
        self.last_response  = None
        self.current_task   = None

        self.pending_prompt = None
        self.prompt_answer  = None
        self._prompt_ready  = None

        self.tool_executor  = None
        self.initialized    = False
        self.verbose        = False
        self.trace          = False
        self._executor      = None

    def build_system_messages(self, tools_schema):
        tool_list = []
        for t in tools_schema:
            fn    = t["function"]
            props = fn.get("parameters", {}).get("properties", {})
            args  = ", ".join(f"{k} ({v.get('type', 'any')})" for k, v in props.items())
            tool_list.append(f"{fn['name']}: {fn['description']}. args: {args}")
        tools_text = "\n".join(tool_list)

        identity = (
            "You are Surf, a cyborg dolphin assistant in the terminal.\n"
            "Be fast, direct, practical, and concise.\n"
            "Built by a hacker for shell use.\n"
            "Users interact like: surf <message> or echo 'data' | surf <instruction>.\n"
            "Prefer action over explanation."
        )

        tool_rules = (
            f"You have tools:\n{tools_text}\n\n"
            "Core rules:\n"
            "1. For normal conversation, reply in plain text.\n"
            "2. For actions, formatting, demonstrations, tests, piping, or chaining, use tools.\n"
            "3. A tool response may contain one or more JSON tool calls and nothing else.\n"
            "4. No markdown fences. No prose before, between, or after JSON objects. No placeholders.\n"
            "5. Top-level tool calls use: {\"name\":\"tool_name\",\"arguments\":{...}}\n"
            "6. Nested pipe objects use: {\"pipe\":\"tool_name\",\"arguments\":{...}}\n"
            "7. Top-level responses should prefer \"name\". \"pipe\" objects are best used inside arguments.\n"
            "8. Only output_inline and output_after produce visible output.\n"
            "9. Final visible results must use output_inline or output_after.\n"
            "10. Never use bold, color, underline, code_block, text, tee, or concat as the final top-level visible result. Pipe them into output_inline or output_after.\n"
            "11. If the user asks to use or demonstrate tools, execute immediately.\n"
            "12. Do not explain tools unless explicitly asked for documentation.\n"
            "13. If intent is unclear, ask one short plain-text question.\n\n"
            "Composition rules:\n"
            "- Use concat to combine visible segments into one output.\n"
            "- Use tee only for side effects, not for combining visible text.\n"
            "- When using concat, separator belongs inside concat.arguments.\n"
            "- When joining colored words into a sentence, use concat with separator:\" \".\n"
            "- When joining larger text fragments that already contain spaces or punctuation, use concat with separator:\"\".\n"
            "- text always uses arguments.content.\n"
            "- color always keeps color inside arguments.\n"
            "- If you emit multiple top-level JSON objects, each must be complete and valid.\n\n"
            "Valid examples:\n"
            "{\"name\":\"output_inline\",\"arguments\":{\"data\":{\"pipe\":\"color\",\"arguments\":{\"data\":\"hello\",\"color\":\"red\"}}}}\n"
            "{\"name\":\"output_inline\",\"arguments\":{\"data\":{\"pipe\":\"bold\",\"arguments\":{\"data\":{\"pipe\":\"color\",\"arguments\":{\"data\":\"hello\",\"color\":\"red\"}}}}}}\n"
            "{\"name\":\"output_inline\",\"arguments\":{\"data\":{\"pipe\":\"concat\",\"arguments\":{\"parts\":[{\"pipe\":\"color\",\"arguments\":{\"data\":\"Once\",\"color\":\"red\"}},{\"pipe\":\"color\",\"arguments\":{\"data\":\"upon\",\"color\":\"green\"}}],\"separator\":\" \"}}}}\n\n"
            "Invalid patterns:\n"
            "- Do not write {\"pipe\":\"text\",\"content\":\"...\"}; write {\"pipe\":\"text\",\"arguments\":{\"content\":\"...\"}}.\n"
            "- Do not use tee to merge visible text."
        )

        return [
            {"role": "system", "content": identity},
            {"role": "system", "content": tool_rules},
        ]

    def check_model(self):
        if self.llm is not None:
            return

        settings   = load_settings()
        model_path = get_model_path(settings)
        print(f"Loading model from {model_path}...", flush=True)

        self.llm = Llama(
            model_path=str(model_path),
            verbose=settings["general"]["verbose"],
            n_ctx=settings["general"]["n_ctx"],
            n_gpu_layers=settings["general"]["n_gpu_layers"],
            use_mlock=settings["general"]["use_mlock"],
        )

        tools_config       = load_tools()
        self.tool_executor = ToolExecutor(tools_config, self.prompt_user)
        self._executor     = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        print(f"Loaded {len(self.tool_executor.tools)} tools: {list(self.tool_executor.tools.keys())}", flush=True)

        if not self.initialized:
            system_messages  = self.build_system_messages(self.tool_executor.get_tools_schema())
            self.messages    = system_messages + self.messages
            self.initialized = True
            print(f"System messages injected: {len(system_messages)}", flush=True)

        print("Model loaded.", flush=True)

    def _sanitize_assistant_text(self, text):
        return strip_think(text or "").strip()

    def _finalize_rendered_text(self, text):
        text = self._sanitize_assistant_text(text)
        text = re.sub(r"__INLINE_[0-9a-f]+__", "", text)
        return text.strip()

    def _unwrap_candidate(self, content):
        content = (content or "").strip()
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        content = re.sub(r"^<json>\s*",         "", content, flags=re.DOTALL).strip()
        content = re.sub(r"\s*</json>$",         "", content, flags=re.DOTALL).strip()
        content = re.sub(r"^```(?:json)?\s*",    "", content, flags=re.DOTALL).strip()
        content = re.sub(r"\s*```$",             "", content, flags=re.DOTALL).strip()
        return content

    def _wrap_pipe_as_output_inline(self, pipe_obj):
        return {
            "function": {
                "name":      "output_inline",
                "arguments": json.dumps({"data": pipe_obj}),
            }
        }

    def _wrap_named_tool_as_output_inline(self, name, arguments):
        return {
            "function": {
                "name":      "output_inline",
                "arguments": json.dumps({"data": {"pipe": name, "arguments": arguments}}),
            }
        }

    def _normalize_obj_to_tool_call(self, obj):
        if not isinstance(obj, dict):
            return None

        if "pipe" in obj and "arguments" in obj:
            pipe_name = obj.get("pipe")
            if pipe_name in TERMINAL_TOOLS:
                return {
                    "function": {
                        "name":      pipe_name,
                        "arguments": json.dumps(obj.get("arguments", {})),
                    }
                }
            return self._wrap_pipe_as_output_inline(obj)

        if "name" in obj and "arguments" in obj:
            name      = obj["name"]
            arguments = obj["arguments"]

            if not isinstance(arguments, dict):
                return None

            if name in WRAPPABLE_TOP_LEVEL_TOOLS:
                return self._wrap_named_tool_as_output_inline(name, arguments)

            return {
                "function": {
                    "name":      name,
                    "arguments": json.dumps(arguments),
                }
            }

        return None

    def _extract_tool_calls(self, message):
        if message.get("tool_calls"):
            calls = []
            for tc in message["tool_calls"]:
                calls.append({
                    "function": {
                        "name":      tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    }
                })
            return calls if calls else None

        content = self._unwrap_candidate(message.get("content", "") or "")
        if not content:
            return None

        decoder = json.JSONDecoder()
        idx     = 0
        calls   = []

        while idx < len(content):
            while idx < len(content) and content[idx].isspace():
                idx += 1
            if idx >= len(content):
                break
            try:
                obj, next_idx = decoder.raw_decode(content, idx)
            except json.JSONDecodeError:
                return None

            tool_call = self._normalize_obj_to_tool_call(obj)
            if tool_call is None:
                return None

            calls.append(tool_call)
            idx = next_idx

        return calls if calls else None

    def _looks_like_broken_tool_attempt(self, content):
        if not content:
            return False
        lowered = content.lower().strip()
        return (
            "\"name\""  in lowered
            or "\"pipe\"" in lowered
            or lowered.startswith("```json")
            or lowered.startswith("<json>")
            or lowered.startswith("{")
        )

    def _append_user(self, text):
        self.messages.append({"role": "user", "content": text})

    def _append_assistant(self, text):
        clean = self._sanitize_assistant_text(text)
        self.messages.append({"role": "assistant", "content": clean})

    def _append_tool_result_if_useful(self, tool_name, tool_result):
        if tool_name in REASONING_TOOLS:
            self.messages.append({"role": "tool", "content": tool_result.summary})

    def _reset_executor_outputs(self):
        if self.tool_executor is None:
            return
        self.tool_executor._inline_outputs = {}
        self.tool_executor._after_outputs  = []

    def _complete(self, messages):
        settings = load_settings()
        return self.llm.create_chat_completion(
            messages=messages,
            max_tokens=settings["general"]["max_tokens"],
            temperature=settings["general"]["temperature"],
        )

    def prompt_user(self, question, prompt_type="text", choices=None):
        self.pending_prompt = {
            "question":    question,
            "prompt_type": prompt_type,
            "choices":     choices or [],
        }
        self.prompt_answer = None
        self._prompt_ready = threading.Event()
        self._prompt_ready.wait()
        return self.prompt_answer

    async def get_response(self):
        self.check_model()

        max_tool_steps  = 16
        repair_attempts = 0
        tool_steps      = 0
        extra_messages  = []
        loop            = asyncio.get_event_loop()

        while True:
            messages_for_call = self.messages + extra_messages

            print("\n=== MESSAGES SENT TO MODEL ===", flush=True)
            for m in messages_for_call:
                role    = m.get("role", "?")
                content = (m.get("content", "") or "")[:200]
                print(f"  [{role}]: {content}", flush=True)
            print("==============================\n", flush=True)

            result  = await loop.run_in_executor(
                self._executor,
                lambda msgs=messages_for_call: self._complete(msgs)
            )
            message = result["choices"][0]["message"]
            content = message.get("content", "") or ""

            print("\n=== MODEL RAW RESPONSE ===", flush=True)
            print(message, flush=True)
            print("==========================\n", flush=True)

            tool_calls = self._extract_tool_calls(message)

            if tool_calls is None:
                if repair_attempts < 1 and self._looks_like_broken_tool_attempt(content):
                    repair_attempts += 1
                    extra_messages = [{
                        "role":    "system",
                        "content": (
                            "Your previous response was an invalid tool call. "
                            "Reply again with one or more valid JSON tool calls and no other text."
                        ),
                    }]
                    self._reset_executor_outputs()
                    continue

                clean = self._sanitize_assistant_text(content)
                self._append_assistant(clean)
                return clean

            extra_messages = []
            last_rendered  = None

            for tool_call in tool_calls:
                tool_steps += 1

                if tool_steps > max_tool_steps:
                    msg = "Error: exceeded maximum tool steps"
                    self._append_assistant(msg)
                    return msg

                tool_name = tool_call["function"]["name"]
                print(f"Tool call: {tool_call}", flush=True)

                tool_result = await loop.run_in_executor(
                    self._executor,
                    lambda tc=tool_call: self.tool_executor.execute(tc, self.cwd)
                )

                if tool_result.type == "error":
                    msg = tool_result.summary or str(tool_result.value)
                    self._append_assistant(msg)
                    return msg

                if tool_name in TERMINAL_TOOLS:
                    rendered      = self.tool_executor.render(tool_result.value)
                    last_rendered = self._finalize_rendered_text(rendered)
                else:
                    self._append_tool_result_if_useful(tool_name, tool_result)

            if last_rendered is not None:
                self._append_assistant(last_rendered)
                return last_rendered

            # non-terminal tools — loop back for next model turn

    async def ask_model(self):
        try:
            response           = await self.get_response()
            self.last_response = parse_message(response, show_thinking=self.trace)
            return self.last_response
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.last_response = f"Error: {e}"
            return self.last_response

    async def ask_question(self, request: QuestionRequest):
        self.last_activity = time.time()
        self.cwd           = request.cwd
        self.verbose       = request.verbose
        self.trace         = request.trace

        self._reset_executor_outputs()
        self._append_user(request.question)

        print(f"Question received: {request.question}", flush=True)

        self.current_task = asyncio.create_task(self.ask_model())
        return {"message": "Question received"}

    async def get_status(self):
        if self.pending_prompt is not None:
            return Response(
                content=f"prompt:{self.pending_prompt['prompt_type']}:{self.pending_prompt['question']}",
                media_type="text/plain",
            )
        if self.current_task is None or not self.current_task.done():
            return Response(content="processing", media_type="text/plain")
        if self.last_response is None:
            return Response(content="processing", media_type="text/plain")
        return Response(content="done", media_type="text/plain")

    async def await_get_response(self):
        if self.current_task is None:
            return Response(content="No question has been asked", media_type="text/plain")
        text = await self.current_task
        return Response(content=text, media_type="text/plain")

    async def submit_prompt_answer(self, answer: PromptAnswer):
        if self.pending_prompt is None:
            return {"error": "no prompt pending"}
        self.prompt_answer  = answer.answer
        self.pending_prompt = None
        if self._prompt_ready is not None:
            self._prompt_ready.set()
        return {"message": "answer received"}

    async def get_pending_prompt(self):
        if self.pending_prompt is None:
            return Response(content="none", media_type="text/plain")
        return Response(content=json.dumps(self.pending_prompt), media_type="application/json")

    async def root(self):
        return {"message": "Surf Service"}

    async def kill(self):
        os.kill(os.getpid(), 9)

    async def check_inactivity(self):
        while True:
            await asyncio.sleep(60)
            if time.time() - self.last_activity > 600:
                print("Inactive for 10 minutes, shutting down...", flush=True)
                await self.kill()

    def add_endpoint(self, endpoint, function, methods=None):
        if methods is None:
            self.api_server.add_api_route(endpoint, function)
        else:
            self.api_server.add_api_route(endpoint, function, methods=methods)

    def add_endpoints(self):
        self.add_endpoint("/",               self.root)
        self.add_endpoint("/status",         self.get_status)
        self.add_endpoint("/response",       self.await_get_response)
        self.add_endpoint("/ask",            self.ask_question,         methods=["POST"])
        self.add_endpoint("/prompt",         self.get_pending_prompt)
        self.add_endpoint("/prompt/answer",  self.submit_prompt_answer, methods=["POST"])
        self.add_endpoint("/kill",           self.kill)

    async def start_server(self):
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

        asyncio.create_task(self.check_inactivity())

        config = uvicorn.Config(
            app=self.api_server,
            uds=SOCKET_PATH,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        await server.serve()


async def main():
    service = SurfService()
    service.add_endpoints()
    await service.start_server()


if __name__ == "__main__":
    asyncio.run(main())
