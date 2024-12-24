import os
import requests
import argparse
import tqdm
import time
import sys
from pathlib import Path
import httpx
from halo import Halo
from .settings import load_settings, settings_exist, edit_settings
import asyncio

settings = {}
own_dir = Path(__file__).parent.absolute()
SOCKET_PATH = "/tmp/dolphin.sock"


def get_client():
    """Create and return HTTP client"""
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=SOCKET_PATH),
        base_url="http://localhost"
    )


def conditional_decorator(dec, condition):
    def decorator(func):
        if not condition:
            # Return the function unchanged, not decorated.
            return func
        return dec(func)

    return decorator


def parse_message(message):
    # replace the tags with the correct color codes
    message = message.replace("[RED]", "\033[31m")
    message = message.replace("[YELLOW]", "\033[33m")
    message = message.replace("[ORANGE]", "\033[33m")
    message = message.replace("[GREEN]", "\033[32m")
    message = message.replace("[PURPLE]", "\033[35m")
    message = message.replace("[BLUE]", "\033[34m")
    message = message.replace("[NORMAL]", "\033[0m")

    # replace all end tags with the normal color code
    message = message.replace("[/RED]", "\033[0m")
    message = message.replace("[/YELLOW]", "\033[0m")
    message = message.replace("[/ORANGE]", "\033[0m")
    message = message.replace("[/GREEN]", "\033[0m")
    message = message.replace("[/PURPLE]", "\033[0m")
    message = message.replace("[/BLUE]", "\033[0m")
    message = message.replace("[/NORMAL]", "\033[0m")

    return message


def init():
    if not model_exists():
        print("Please select a model")
        download_model(select_model())

    if not settings_exist():
        print("Please make sure the settings are correct")
        settings = load_settings()  # noqa: F841
        exit(1)


def main():
    """Main entry point for the application"""
    init()

    # parse the arguments
    parser = argparse.ArgumentParser(description="AskSurf CLI")
    parser.add_argument(
        "question",
        nargs=argparse.REMAINDER,
        help="The question to ask Dolphin",
    )
    parser.add_argument(
        "--model",
        "-m",
        action="store_true",
        help="The model to use",
    )
    parser.add_argument(
        "--delete",
        "-d",
        action="store_true",
        help="Delete the model",
    )
    parser.add_argument(
        "--kill",
        "-k",
        action="store_true",
        help="Kill the Dolphin service",
    )
    parser.add_argument(
        "--settings",
        "-s",
        action="store_true",
        help="Edit the settings",
    )
    args = parser.parse_args()

    if args.model:
        download_model(select_model())
        return

    if args.delete:
        delete_model()
        return

    if args.kill:
        client = httpx.AsyncClient(transport=httpx.HTTPTransport(uds=SOCKET_PATH))
        client.get("/kill")
        return

    if args.settings:
        edit_settings()
        # Restart service after settings change
        if check_dolphin_service():
            client = httpx.AsyncClient(transport=httpx.HTTPTransport(uds=SOCKET_PATH))
            client.get("/kill")
        return
    # Join the list of arguments into a single string
    question = " ".join(args.question)

    # If stdin is not empty, append it to the question
    if not sys.stdin.isatty():
        question += " " + sys.stdin.read()

    # Run async code
    def run():
        while not check_dolphin_service():
            start_dolphin_service()
            # Wait for service to start
            time.sleep(5)
        
        result = ask_dolphin(question)
        print(result)

    asyncio.run(run())


def check_dolphin_service():
    """Check if FastAPI service is running"""
    client = get_client()
    try:
        client.get("/")
        return True
    except:
        return False


def start_dolphin_service():
    """Start the FastAPI dolphin service"""
    path = own_dir / "dolphin_service.py"
    os.system(f"nohup python3 {path} > /dev/null 2>&1 &")


@conditional_decorator(Halo(text="Asking Surf...", spinner="dots"), sys.stdout.isatty())
def ask_dolphin(question):
    """Ask a question to Dolphin"""
    client = get_client()
    
    client.post("/ask", json={
        "question": question,
        "cwd": os.getcwd()
    })

    while True:
        status_response = client.get("/status")
        status = status_response.json()
        if status != "processing":
            break
        time.sleep(0.5)

    result = client.get("/response")
    return parse_message(result.json())



def select_model():
    """Select a model"""
    models = [
        {
            "name": "dolphin-2.7-mixtral-8x7b.Q2_K.gguf",
            "description": "smallest, significant quality loss - not recommended for most purposes",
        },
        {
            "name": "dolphin-2.7-mixtral-8x7b.Q3_K_M.gguf",
            "description": "very small, high quality loss",
        },
        {
            "name": "dolphin-2.7-mixtral-8x7b.Q4_0.gguf",
            "description": "legacy; small, very high quality loss - prefer using Q3_K_M",
        },
        {
            "name": "dolphin-2.7-mixtral-8x7b.Q4_K_M.gguf",
            "description": "medium, balanced quality - recommended",
        },
        {
            "name": "dolphin-2.7-mixtral-8x7b.Q5_0.gguff",
            "description": "legacy; medium, balanced quality - prefer using Q4_K_M",
        },
        {
            "name": "dolphin-2.7-mixtral-8x7b.Q5_K_M.gguf",
            "description": "large, very low quality loss - recommended",
        },
        {
            "name": "dolphin-2.7-mixtral-8x7b.Q6_K.gguf",
            "description": "very large, extremely low quality loss",
        },
        {
            "name": "dolphin-2.7-mixtral-8x7b.Q8_0.gguf",
            "description": "very large, extremely low quality loss - not recommended",
        },
    ]

    print("Select a model:")
    for i, model in enumerate(models):
        print(f"{i + 1}. {model['name']} - {model['description']}")

    while True:
        try:
            selection = int(input("Selection: "))
            if selection < 1 or selection > len(models):
                raise ValueError()
            break
        except ValueError:
            print("Invalid selection")

    return models[selection - 1]["name"]


def delete_model():
    """Delete the model"""
    os.remove(own_dir / "model.gguf")


def model_exists():
    """Check if the model exists"""
    return os.path.exists(own_dir / "model.gguf")


def download_model(name):
    """Download the model from the server"""
    url = f"https://huggingface.co/TheBloke/dolphin-2.7-mixtral-8x7b-GGUF/resolve/main/{name}?download=true"

    # check if the file exists
    if model_exists():
        delete_model()

    # download the file
    r = requests.get(url, stream=True)
    total_size = int(r.headers.get("content-length", 0))
    block_size = 1024
    t = tqdm.tqdm(total=total_size, unit="iB", unit_scale=True)
    with open(own_dir / "model.gguf", "wb") as f:
        for data in r.iter_content(block_size):
            t.update(len(data))
            f.write(data)


if __name__ == "__main__":
    main()
