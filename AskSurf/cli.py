import os
import requests
import argparse
import tqdm
import time
import subprocess
import sys
from pathlib import Path
from halo import Halo
from settings import load_settings, settings_exist, edit_settings
from contextlib import redirect_stdout, redirect_stderr

# This should only be loaded when an image is about to be generated
with open('/dev/null', 'w') as null_file:
    with redirect_stdout(null_file), redirect_stderr(null_file):
        from .generate_image import generate_image

settings = {}
own_dir = Path(__file__).parent.absolute()
question_pipe = own_dir / "question_pipe"
response_pipe = own_dir / "response_pipe"


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

def limit_str_len(input_string, max_length):
    if len(input_string) > max_length:
        truncated_string = input_string[:max_length]
        return truncated_string
    else:
        return input_string
    
def parse_images(message):
    message.replace("[image]", "[IMAGE]")
    message.replace("[/image]", "[/IMAGE]")
    message = message.split("[IMAGE]")
    i = 1
    for section in message:
        #print(message)
        section = section.split("[/IMAGE]")
        for subsection in section:
            if i % 2 == 0:
                with Halo(text='Drawing Image', spinner='dots'):
                    name = generate_image(limit_str_len(subsection, 77))
                path = os.path.join(os.getcwd(), name)
                subprocess.run(['/usr/bin/viu', path])
                print(f'{name} : {subsection}')
            else: 
                print(subsection.rstrip())
        
            i += 1

def init():
    if not model_exists():
        print("Please select a model")
        download_model(select_model())

    if not settings_exist():
        print("Please make sure the settings are correct")
        settings = load_settings()
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
        os.system("pkill -f dolphin_service.py")
        exit(0)

    if args.settings:
        edit_settings()
        os.system("pkill -f dolphin_service.py")
        return

    # Join the list of arguments into a single string
    question = " ".join(args.question)

    # If stdin is not empty, append it to the question
    if not sys.stdin.isatty():
        question += " " + sys.stdin.read()

    if not check_dolphin_service_running():
        start_dolphin_service()

    # ask the question
    parse_images(parse_message(ask_dolphin(question)))


def check_dolphin_service_running():
    """Check if the Dolphin service is running"""
    try:
        # Use subprocess to run the command and capture output
        output = subprocess.check_output(["ps", "-aux"]).decode("utf-8")

        # Check if "dolphin_service.py" is in the output
        if "dolphin_service.py" in output:
            return True

    except subprocess.CalledProcessError:
        return False

    return False


def start_dolphin_service():
    """Start the Dolphin service"""
    # start the service
    path = own_dir / "dolphin_service.py"
    os.system(f"nohup python3 {path} > /dev/null 2>&1 &")


@conditional_decorator(Halo(text="Asking Surf...", spinner="dots"), sys.stdout.isatty())
def ask_dolphin(question):
    """Ask a question to Dolphin"""
    # Make sure the anwser pipe is empty
    with open(response_pipe, "w") as f:
        f.write("")

    # Write the question to the question_pipe
    with open(question_pipe, "w") as f:
        f.write(question)

    # wait for the response
    while True:
        # Check if the response_pipe has any content
        with open(response_pipe, "r") as f:
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
