import os
import requests
import argparse
import tqdm
import time
import subprocess
import sys
from pathlib import Path

own_dir = Path(__file__).parent.absolute()

def parse_message(message):
    # replace the tags with the correct color codes
    message = message.replace("[RED]", "\033[31m")
    message = message.replace("[YELLOW]", "\033[33m")
    message = message.replace("[GREEN]", "\033[32m")
    message = message.replace("[PURPLE]", "\033[35m")
    message = message.replace("[BLUE]", "\033[34m")
    message = message.replace("[NORMAL]", "\033[0m")

    return message

def main():
    """Main entry point for the application"""
    # download the model
    if not model_exists():
        download_model(select_model())
        return

    # parse the arguments
    parser = argparse.ArgumentParser(description="AskSurf CLI")
    parser.add_argument(
        "question",
        nargs="+",
        help="The question to ask Dolphin",
    )
    parser.add_argument(
        "--model",
        "-m",
        help="The model to use",
    )
    args = parser.parse_args()

    if args.model:
        download_model(select_model())
        return

    # Join the list of arguments into a single string
    question = " ".join(args.question)

    # If stdin is not empty, add a newline and the stdin to the question
    if not sys.stdin.isatty():
        question += ":\n"
        for line in sys.stdin:
            question += line

    if not check_dolphin_service_running():
        start_dolphin_service()

    # ask the question
    print(parse_message(ask_dolphin(question)))


def check_dolphin_service_running():
    """Check if the Dolphin service is running"""
    try:
        # Use subprocess to run the command and capture output
        output = subprocess.check_output(["ps", "-aux"]).decode("utf-8")

        # Check if "dolphin_service.py" is in the output
        if "dolphin_service.py" in output:
            return True

    except subprocess.CalledProcessError:
        pass

    return False


def start_dolphin_service():
    """Start the Dolphin service"""

    try:
        # create the question_pipe
        os.mkfifo(own_dir / "question_pipe")
    except FileExistsError:
        pass

    try:
        # create the response_pipe
        os.mkfifo(own_dir / "response_pipe")
    except FileExistsError:
        pass

    # start the service
    os.system("nohup python src/dolphin_service.py > /dev/null 2>&1 &")


def ask_dolphin(question):
    """Ask a question to Dolphin"""
    # Make sure the anwser pipe is empty
    with open(own_dir / "response_pipe", "w") as f:
        f.write("")

    # Write the question to the question_pipe
    with open(own_dir / "question_pipe", "w") as f:
        f.write(question)

    # wait for the response
    while True:
        # Check if the response_pipe has any content
        with open(own_dir / "response_pipe", "r") as f:
            content = f.read()

        if not content:
            time.sleep(1)
            continue

        # return the response
        return content


def select_model():
    """Select a model"""
    models = [
        {
            "name": "dolphin-2.5-mixtral-8x7b.Q2_K.gguf",
            "description": "smallest, significant quality loss - not recommended for most purposes",
        },
        {
            "name": "dolphin-2.5-mixtral-8x7b.Q3_K_M.gguf",
            "description": "very small, high quality loss",
        },
        {
            "name": "dolphin-2.5-mixtral-8x7b.Q4_0.gguf",
            "description": "legacy; small, very high quality loss - prefer using Q3_K_M",
        },
        {
            "name": "dolphin-2.5-mixtral-8x7b.Q4_K_M.gguf",
            "description": "medium, balanced quality - recommended",
        },
        {
            "name": "dolphin-2.5-mixtral-8x7b.Q5_0.gguf",
            "description": "legacy; medium, balanced quality - prefer using Q4_K_M",
        },
        {
            "name": "dolphin-2.5-mixtral-8x7b.Q5_K_M.gguf",
            "description": "large, very low quality loss - recommended",
        },
        {
            "name": "dolphin-2.5-mixtral-8x7b.Q6_K.gguf",
            "description": "very large, extremely low quality loss",
        },
        {
            "name": "dolphin-2.5-mixtral-8x7b.Q8_0.gguf",
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
    url = f"https://huggingface.co/TheBloke/dolphin-2.5-mixtral-8x7b-GGUF/resolve/main/{name}?download=true"

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
