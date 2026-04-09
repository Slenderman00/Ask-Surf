import os
import sys
import time
import json
import argparse
from pathlib import Path
import httpx
from halo import Halo
from .settings import load_settings, settings_exist, edit_settings, resolve_model, get_model_path
from .utility import detect_file_type, extract_text_from_pdf, extract_text_from_docx, is_mimetype_docx, parse_message


own_dir     = Path(__file__).parent.absolute()
SOCKET_PATH = "/tmp/surf.sock"


def get_client():
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=SOCKET_PATH),
        base_url="http://localhost",
    )


def conditional_decorator(dec, condition):
    def decorator(func):
        if not condition:
            return func
        return dec(func)
    return decorator


def check_surf_service():
    try:
        get_client().get("/", timeout=2)
        return True
    except:
        return False


def start_surf_service():
    path = own_dir / "dolphin_service.py"
    os.system(f"nohup python3 {path} > /dev/null 2>&1 &")


def kill_surf_service():
    try:
        get_client().get("/kill")
    except:
        pass


def handle_pending_prompt(client):
    """check if the service is waiting for user input and handle it"""
    response = client.get("/prompt", timeout=10)
    if response.text == "none":
        return

    try:
        prompt = json.loads(response.text)
    except:
        return

    question    = prompt.get("question", "")
    prompt_type = prompt.get("prompt_type", "text")
    choices     = prompt.get("choices", [])

    print()

    if prompt_type == "confirm":
        while True:
            answer = input(f"  {question} [y/n]: ").strip().lower()
            if answer in ("y", "yes"):
                answer = "true"
                break
            elif answer in ("n", "no"):
                answer = "false"
                break
            print("  Please answer y or n")

    elif prompt_type == "choice":
        print(f"  {question}")
        for i, choice in enumerate(choices, 1):
            print(f"  {i}. {choice}")
        while True:
            try:
                idx = int(input(f"  Select [1-{len(choices)}]: ").strip()) - 1
                if 0 <= idx < len(choices):
                    answer = choices[idx]
                    break
            except (ValueError, KeyboardInterrupt):
                pass
            print(f"  Please enter a number between 1 and {len(choices)}")

    else:
        answer = input(f"  {question}: ").strip()

    print()

    client.post("/prompt/answer", json={"answer": answer}, timeout=10)


def ask_surf(question, verbose=False, trace=False):
    client  = get_client()
    spinner = Halo(text="Asking Surf...", spinner="dots")

    if sys.stdout.isatty():
        spinner.start()

    response = client.post("/ask", json={
        "question": question,
        "cwd":      os.getcwd(),
        "verbose":  verbose,
        "trace":    trace,
    }, timeout=6000)

    if response.status_code != 200:
        spinner.stop()
        raise Exception(f"Failed to send question: HTTP {response.status_code}")

    while True:
        status_response = client.get("/status", timeout=6000)

        if status_response.status_code != 200:
            spinner.stop()
            raise Exception(f"Failed to get status: HTTP {status_response.status_code}")

        status = status_response.text

        if status.startswith("prompt:"):
            spinner.stop()
            handle_pending_prompt(client)
            if sys.stdout.isatty():
                spinner.start()
            continue

        if status == "done":
            break

        time.sleep(0.5)

    spinner.stop()

    result = client.get("/response", timeout=6000)

    if result.status_code != 200:
        raise Exception(f"Failed to get response: HTTP {result.status_code}")

    return parse_message(result.text)


def init():
    # resolve and download happen here in the foreground so the
    # progress bar is visible — the service never needs to download
    settings = load_settings()
    settings = resolve_model(settings)
    get_model_path(settings)


def main():
    parser = argparse.ArgumentParser(description="Surf CLI", add_help=True)

    parser.add_argument(
        "prompt",
        nargs=argparse.REMAINDER,
        help="The prompt to send to Surf",
    )
    parser.add_argument(
        "--kill", "-k",
        action="store_true",
        help="Kill the Surf service",
    )
    parser.add_argument(
        "--settings", "-s",
        action="store_true",
        help="Edit settings",
    )
    parser.add_argument(
        "--model", "-m",
        action="store_true",
        help="Pick and download a new model",
    )
    parser.add_argument(
        "--delete", "-d",
        action="store_true",
        help="Delete the current model",
    )
    parser.add_argument(
        "--last", "-l",
        action="store_true",
        help="Show the last response",
    )
    parser.add_argument(
        "-v",
        action="store_true",
        help="Verbose — show tool calls and arguments as they execute",
    )
    parser.add_argument(
        "-x",
        action="store_true",
        help="Trace — show full pipe resolution tree with inputs and outputs",
    )

    args = parser.parse_args()

    if args.kill:
        kill_surf_service()
        return

    if args.settings:
        edit_settings()
        # restart so the service picks up new settings
        if check_surf_service():
            kill_surf_service()
        return

    if args.model:
        from .settings import pick_model_file, save_settings
        settings = load_settings()
        chosen   = pick_model_file(settings["general"]["model_repo"])
        settings["general"]["model_file"] = chosen
        save_settings(settings)
        # kill so the service reloads with the new model
        if check_surf_service():
            kill_surf_service()
        return

    if args.delete:
        from .settings import load_settings as ls, save_settings as ss, MODELS_DIR
        settings = ls()
        model_file = settings["general"].get("model_file", "")
        if model_file:
            path = MODELS_DIR / Path(model_file).name
            if path.exists():
                path.unlink()
                print(f"Deleted {path}")
            settings["general"]["model_file"] = ""
            ss(settings)
        return

    if args.last:
        try:
            response = get_client().get("/response", timeout=10)
            print(parse_message(response.text))
        except:
            print("No response available")
        return

    init()

    # build the prompt from positional args
    question = " ".join(args.prompt).strip()

    # prepend stdin if piped
    if not sys.stdin.isatty():
        data = sys.stdin.buffer.read()
        mime = detect_file_type(data)

        if mime == "application/pdf":
            stdin_text = extract_text_from_pdf(data)
        elif mime == "text/plain":
            stdin_text = data.decode("utf-8")
        elif is_mimetype_docx(mime):
            stdin_text = extract_text_from_docx(data)
        else:
            stdin_text = data.decode("utf-8", errors="replace")

        if question:
            question = stdin_text + "\n" + question
        else:
            question = stdin_text

    if not question:
        parser.print_help()
        return

    # start the service if it isn't running
    if not check_surf_service():
        print("Starting Surf...")
        start_surf_service()
        while not check_surf_service():
            time.sleep(1)

    result = ask_surf(question, verbose=args.v, trace=args.x)
    print(result)


if __name__ == "__main__":
    main()
