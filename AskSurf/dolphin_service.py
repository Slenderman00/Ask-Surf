from llama_cpp import Llama
import os
import time

own_dir = Path(__file__).parent.absolute()

def generate_prompt(messages):
    output = ""

    for message in messages:
        output += f"<|im_start|>{message['role']}\n {message['content']}<|im_end|>\n"

    output += "<|im_start|>assistant\n"

    return output


last_used = time.time()


try:
    # create the question_pipe
    os.mkfifo("./question_pipe")
except FileExistsError:
    pass

try:
    # create the response_pipe
    os.mkfifo("./response_pipe")
except FileExistsError:
    pass


llm = Llama(
    model_path=own_dir / "model.gguf",
    chat_format="llama-2",
    verbose=False,
    use_mlock=True,
    n_ctx=2048,
)

messages = [
    {
        "role": "system",
        "content": "You are a trained dolphin assistant. Your name is Surf",
    },
    {
        "role": "system",
        "content": "You can use the following tags: [RED], [YELLOW], [GREEN], [PURPLE], [BLUE], [NORMAL].",
    },
    {
        "role": "system",
        "content": "Users interact with you by running the 'surf' cli command, users can also pipe data to you \"echo 'Hello' | surf 'Do something with this'\"",
    },
]

while True:
    # Check if the question_pipe has any content
    with open("./question_pipe", "r") as f:
        content = f.read().strip()

    if not content:
        print("Waiting for a question...")
        time.sleep(1)

        # check if the question_pipe has been inactive for 15 minutes
        if time.time() - last_used > 60 * 15:
            print("No questions for 15 minutes, shutting down...")
            break

        continue

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
        max_tokens=1024,
        temperature=0.9,
        top_p=1,
        frequency_penalty=0.02,
        presence_penalty=0.01,
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
    with open("./response_pipe", "w") as f:
        f.write(anwser["choices"][0]["text"])

    # wait a bit
    time.sleep(1)
