from llama_cpp import Llama
import os
import time
from pathlib import Path
from settings import load_settings

own_dir = Path(__file__).parent.absolute()
settings = load_settings()
question_pipe = own_dir / "question_pipe"
response_pipe = own_dir / "response_pipe"


def generate_prompt(messages):
    output = ""

    for message in messages:
        output += f"<|im_start|>{message['role']}\n {message['content']}<|im_end|>\n"

    output += "<|im_start|>assistant\n"

    return output


last_used = time.time()

try:
    # create the question_pipe
    os.mkfifo(question_pipe)
except FileExistsError:
    pass

try:
    # create the response_pipe
    os.mkfifo(response_pipe)
except FileExistsError:
    pass

success = False
while not success:
    try:
        llm = Llama(
            model_path=settings["general"]["model_path"],
            verbose=settings["general"]["verbose"],
            n_ctx=settings["general"]["n_ctx"],
            n_gpu_layers=settings["general"]["n_gpu_layers"],
            use_nmap=settings["general"]["use_nmap"],
            use_mlock=settings["general"]["use_mlock"],
        )
        success = True
    except RuntimeError:
        print("Failed to load model, retrying in 5 seconds...")
        time.sleep(5)
        continue


messages = [
    {
        "role": "system",
        "content": "You are a trained dolphin assistant. Your name is Surf",
    },
    {
        "role": "system",
        "content": "You can use the following tags: [RED], [YELLOW], [ORANGE], [GREEN], [PURPLE], [BLUE], [NORMAL], [IMAGE]",
    },
    {
        "role": "system",
        "content": "The image tag: [IMAGE]description 1, description 2, description 3[/IMAGE] creates an image based on the the description tags and appends it to the text. DO NOT FORGET THE CLOSE TAG",
    },
    {
        "role": "system",
        "content": "Image tags can be inserted into text like this: this is text [IMAGE]blue eyes, green hair, tall, blue sky[/IMAGE] this is more text [IMAGE]Large tree, dark, scary[/IMAGE]. Note that text can have multiple image tags",
    },
    {
        "role": "system",
        "content": "Image tags must be used when the user asks for drawing, picture or image",
    },
    {
        "role": "system",
        "content": "Users interact with you by running the 'surf' cli command, users can also pipe data to you \"echo 'Hello' | surf 'Do something with this'\"",
    },
]

while True:
    # Check if the question_pipe has any content
    with open(question_pipe, "r") as f:
        content = f.read().strip()
        print(content)

    if not content:
        print("Waiting for a question...")
        time.sleep(1)

        # check if the question_pipe has been inactive for 15 minutes
        if time.time() - last_used > 60 * 15:
            print("No questions for 15 minutes, shutting down...")
            break

        continue

    # clear the question_pipe
    with open(question_pipe, "w") as f:
        f.write("")

    # update the last_used time
    last_used = time.time()

    print(f"'{content}' received!")

    messages.append(
        {
            "role": "user",
            "content": content,
        }
    )

    # ask the question
    anwser = llm(
        generate_prompt(messages),
        max_tokens=settings["general"]["max_tokens"],
        temperature=settings["general"]["temperature"],
        top_p=settings["general"]["top_p"],
        frequency_penalty=settings["general"]["frequency_penalty"],
        presence_penalty=settings["general"]["presence_penalty"],
        stop=["<|im_end|>"],
    )

    print(f"'{anwser['choices'][0]['text']}' anwsered!")

    if anwser["choices"][0]["text"] == "":
        anwser["choices"][0]["text"] = "I am sorry, I do not understand your question."

    messages.append(
        {
            "role": "assistant",
            "content": anwser["choices"][0]["text"],
        }
    )

    # write the anwser to the response_pipe
    with open(response_pipe, "w") as f:
        f.write(anwser["choices"][0]["text"])

    # wait a bit
    time.sleep(1)
