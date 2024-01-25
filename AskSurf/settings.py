import toml
import os
from pathlib import Path


own_dir = Path(__file__).parent.absolute()

settings = {
    "general": {
        "model_path": str(own_dir / "model.gguf"),
        "verbose": True,
        "n_ctx": 4096,
        "n_gpu_layers": 0,
        "use_nmap": True,
        "use_mlock": False,
        "max_tokens": 4096,
        "temperature": 0.7,
        "top_p": 1,
        "frequency_penalty": 0.02,
        "presence_penalty": 0.01,
        "image_model": "stabilityai/stable-diffusion-2"
    }
}


def create_settings():
    # create the settings.toml file
    with open(own_dir / "settings.toml", "w") as f:
        toml.dump(settings, f)


def select_editor():
    editors = ["vim", "nano", "emacs", "code"]
    for i, editor in enumerate(editors):
        print(f"{i}: {editor}")

    while True:
        try:
            choice = int(input("Select an editor: "))
            if choice < 0 or choice >= len(editors):
                raise ValueError
            break
        except ValueError:
            print("Invalid choice")

    return editors[choice]


def edit_settings():
    os.system(f"{select_editor()} {own_dir / 'settings.toml'}")


def settings_exist():
    return (own_dir / "settings.toml").exists()


def load_settings():
    # check if settings.toml exists
    if not settings_exist():
        create_settings()
        edit_settings()
        return load_settings()

    with open(own_dir / "settings.toml", "r") as f:
        settings = toml.load(f)

    return settings
