  
# Ask Surf 🐬

Surf is a CLI wrapper for llama_cpp_python used to interact with and mangage [TheBloke/dolphin-2.5-mixtral-8x7b-GGUF](https://huggingface.co/TheBloke/dolphin-2.5-mixtral-8x7b-GGUF)

```
surf introduce yourself to github
```

```
Hello Github! I'm Surf, 
a friendly trained dolphin assistant here to help you with your coding needs. 
As an AI, I can understand and execute simple code snippets in multiple languages, including 
Python, JavaScript, and HTML. 
If you ever need assistance with coding tasks or debugging issues, just send me a message. 
Happy coding!
```
---

```
surf explain how you work
```

```
My main function is to assist users in processing and manipulating data. 
To interact with me, users can use the 'surf' command followed by any of the available tags or 
directly input the data they wish for me to process.

For example, if a user types "echo 'Hello' | surf 'process this text'", I will identify the 
input text as 'Hello', 
apply the RED color filter, and provide the resulting output.

I am designed to handle various commands and filters, which include changing colors 
(RED, YELLOW, GREEN, PURPLE, BLUE), 
resetting formatting (NORMAL), or even performing specific actions such as counting 
occurrences of words in a given text. 
My goal is to help users process data more efficiently and effectively.
```


## Usage

Both of the following are valid.
```
surf tell me a joke
```
or
```
surf "tell me a joke"
```
You can pipe the text into the `surf` command followed by the action you want to perform. For example:

```bash
surf -h | surf 'Write a usage section for your own readme.md, this will be piped' > usage.md
```

This command will prompt Surf to generate a settings section for the given text. You can also use the provided options (e.g., `-m`, `-d`, `-k`) with their respective actions (e.g., "--model", "--delete", "--kill") as needed:

```bash
surf [-h] [--model] [--delete] [--kill] [--settings] ...
```


## Installation

Surf can be installed by following these two simple steps.

- make sure to install [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
- ```pip install git+https://github.com/Slenderman00/Ask-Surf.git#egg=asksurf ```

---
When surf is initially run you will be promted to select the model you want to download.
