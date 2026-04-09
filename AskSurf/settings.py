import requests
import tqdm
import toml
import os
import re
import subprocess
from pathlib import Path
from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError


CONFIG_DIR    = Path.home() / ".config" / "surf"
SETTINGS_FILE = CONFIG_DIR / "settings.toml"
TOOLS_FILE    = CONFIG_DIR / "tools.toml"
MODELS_DIR    = CONFIG_DIR / "models"

DEFAULT_SETTINGS = {
    "general": {
        "model_repo":   "HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive",
        "model_file":   "",
        "models_dir":   str(MODELS_DIR),
        "verbose":      False,
        "n_ctx":        8192,
        "n_gpu_layers": -1,
        "use_mlock":    False,
        "max_tokens":   4096,
        "temperature":  0.7,
        "tool_verbose": False,
    }
}

DEFAULT_TOOLS = {
    "fetch_url":      {"enabled": True, "timeout": 30, "user_agent": "surf/3.0"},
    "search":         {"enabled": True, "base_url": "http://127.0.0.1:8888", "engines": ""},
    "save_file":      {"enabled": True},
    "read_file":      {"enabled": True},
    "to_model":       {"enabled": True},
    "image_to_cli":   {"enabled": True, "width": 100},
    "create_table":   {"enabled": True, "style": "unicode"},
    "tee":            {"enabled": True},
    "output_inline":  {"enabled": True},
    "output_after":   {"enabled": True},
    "text":           {"enabled": True},
    "concat":         {"enabled": True},
    "code_block":     {"enabled": True},
    "color":          {"enabled": True},
    "underline":      {"enabled": True},
    "bold":           {"enabled": True},
    "ask_user":       {"enabled": True},
    "nmap":           {"enabled": True, "require_confirm": True, "default_flags": "-sV"},
}

QUANT_DESCRIPTIONS = {
    "IQ1_S":   "extremely small, severe quality loss",
    "IQ1_M":   "extremely small, severe quality loss",
    "IQ2_XXS": "very small, major quality loss",
    "IQ2_XS":  "very small, major quality loss",
    "IQ2_S":   "very small, major quality loss",
    "IQ2_M":   "very small, major quality loss",
    "Q2_K":    "smallest K-quant, significant quality loss",
    "IQ3_XXS": "small, high quality loss",
    "IQ3_XS":  "small, high quality loss",
    "IQ3_S":   "small, high quality loss",
    "IQ3_M":   "small, high quality loss",
    "Q3_K_S":  "small, high quality loss",
    "Q3_K_M":  "small, high quality loss",
    "Q3_K_L":  "small, moderate quality loss",
    "IQ4_XS":  "medium, good quality",
    "IQ4_NL":  "medium, good quality",
    "Q4_0":    "legacy 4-bit, moderate quality loss",
    "Q4_K_S":  "medium, balanced quality",
    "Q4_K_M":  "medium, balanced quality — recommended",
    "Q5_0":    "legacy 5-bit, low quality loss",
    "Q5_K_S":  "large, very low quality loss",
    "Q5_K_M":  "large, very low quality loss — recommended",
    "Q6_K":    "very large, minimal quality loss",
    "Q8_0":    "maximum quality, largest size",
}

RECOMMENDED_QUANTS = {"Q4_K_M", "Q5_K_M"}


def get_available_vram_gb():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            mb = int(result.stdout.strip().split("\n")[0])
            return mb / 1024
    except Exception:
        pass
    return None


def format_size(size_bytes):
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / 1024 ** 3:.1f} GB"
    elif size_bytes >= 1024 ** 2:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def parse_quant(filename):
    upper = filename.upper()
    # longest match first so Q4 doesn't swallow Q4_K_M
    for quant in sorted(QUANT_DESCRIPTIONS.keys(), key=len, reverse=True):
        if quant in upper:
            return quant
    return None


def fetch_repo_files(repo_id, retries=5):
    """fetch gguf file list from huggingface with retry on 429"""
    import time
    api = HfApi()
    for attempt in range(retries):
        try:
            return list(api.list_repo_tree(repo_id, expand=True))
        except RepositoryNotFoundError:
            raise RuntimeError(f"Repository not found: {repo_id}")
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                wait = 2 ** attempt
                print(f"Rate limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Failed to fetch repo file list: {e}")


def pick_model_file(repo_id):
    print(f"\nFetching file list from {repo_id}...")

    files = fetch_repo_files(repo_id)

    gguf_files = []
    for f in files:
        name = getattr(f, "path", "") or getattr(f, "rfilename", "")
        if not name.lower().endswith(".gguf"):
            continue
        # skip non-first shards
        if re.search(r"-\d{5}-of-\d{5}\.gguf$", name) and not name.endswith("-00001-of-00003.gguf"):
            continue
        size = 0
        if hasattr(f, "size") and f.size:
            size = f.size
        gguf_files.append({"name": name, "size": size})

    if not gguf_files:
        raise RuntimeError(f"No GGUF files found in {repo_id}")

    gguf_files.sort(key=lambda x: x["size"] or 0)

    vram = get_available_vram_gb()

    print(f"\nAvailable quants for {repo_id}:\n")

    col_num   = 4
    col_name  = 55
    col_size  = 9
    col_quant = 12

    for i, f in enumerate(gguf_files, 1):
        name     = f["name"]
        size     = f["size"]
        quant    = parse_quant(name) or "unknown"
        desc     = QUANT_DESCRIPTIONS.get(quant, "")
        size_str = format_size(size) if size else "unknown"
        fit      = ""

        if vram and size:
            size_gb = size / 1024 ** 3
            if size_gb <= vram - 1:
                fit = " ✓"
            elif size_gb <= vram:
                fit = " ~"
            else:
                fit = " ✗"

        marker = (" ★" if quant in RECOMMENDED_QUANTS else "") + fit
        if marker.strip():
            marker = f"  [{marker.strip()}]"

        display_name = name if len(name) <= col_name - 1 else "..." + name[-(col_name - 4):]

        print(
            f"  {i:<{col_num}}"
            f"{display_name:<{col_name}}"
            f"{size_str:>{col_size}}"
            f"  {quant:<{col_quant}}"
            f"  {desc}"
            f"{marker}"
        )

    print()
    if vram:
        print(f"  Detected VRAM: {vram:.1f} GB   ✓ fits  ~ tight  ✗ too large  ★ recommended quant")
    else:
        print("  ★ = recommended quant  (could not detect VRAM)")
    print()

    while True:
        try:
            idx = int(input(f"  Select [1-{len(gguf_files)}]: ").strip()) - 1
            if 0 <= idx < len(gguf_files):
                chosen = gguf_files[idx]["name"]
                print(f"\n  Selected: {chosen}\n")
                return chosen
        except (ValueError, KeyboardInterrupt):
            pass
        print(f"  Please enter a number between 1 and {len(gguf_files)}")


def select_editor():
    if "EDITOR" in os.environ:
        return os.environ["EDITOR"]
    for editor in ["vim", "nano", "emacs", "micro", "code"]:
        if subprocess.run(["which", editor], capture_output=True).returncode == 0:
            return editor
    raise RuntimeError("No editor found. Set the EDITOR environment variable.")


def edit_settings():
    os.system(f"{select_editor()} {SETTINGS_FILE}")


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def settings_exist():
    return SETTINGS_FILE.exists()


def tools_exist():
    return TOOLS_FILE.exists()


def create_settings():
    ensure_config_dir()
    with open(SETTINGS_FILE, "w") as f:
        toml.dump(DEFAULT_SETTINGS, f)


def create_tools():
    ensure_config_dir()
    with open(TOOLS_FILE, "w") as f:
        toml.dump(DEFAULT_TOOLS, f)


def load_settings():
    ensure_config_dir()

    if not settings_exist():
        create_settings()

    with open(SETTINGS_FILE, "r") as f:
        settings = toml.load(f)

    # deep merge so new default keys are always present
    merged = DEFAULT_SETTINGS.copy()
    for section, values in settings.items():
        if section in merged and isinstance(merged[section], dict):
            merged[section] = {**merged[section], **values}
        else:
            merged[section] = values

    return merged


def load_tools():
    ensure_config_dir()

    if not tools_exist():
        create_tools()

    with open(TOOLS_FILE, "r") as f:
        return toml.load(f)


def save_settings(settings):
    ensure_config_dir()
    with open(SETTINGS_FILE, "w") as f:
        toml.dump(settings, f)


def resolve_model(settings):
    """if model_file is not set, prompt the user to pick one and save it"""
    model_file = settings["general"].get("model_file", "").strip()

    if not model_file:
        repo   = settings["general"]["model_repo"]
        chosen = pick_model_file(repo)
        settings["general"]["model_file"] = chosen
        save_settings(settings)
        print(f"Saved model selection to {SETTINGS_FILE}\n")

    return settings


def get_hf_download_url(repo, filename):
    return f"https://huggingface.co/{repo}/resolve/main/{filename}?download=true"


def get_model_path(settings):
    """return local path to model file, downloading with progress bar if needed"""
    models_dir = Path(settings["general"]["models_dir"]).expanduser()
    models_dir.mkdir(parents=True, exist_ok=True)

    model_file = settings["general"]["model_file"]
    model_path = models_dir / Path(model_file).name

    if not model_path.exists():
        repo = settings["general"]["model_repo"]
        url  = get_hf_download_url(repo, model_file)

        print(f"Downloading {model_file}...")

        tmp_path = model_path.with_suffix(".part")

        try:
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()

            total = int(r.headers.get("content-length", 0))

            with tqdm.tqdm(total=total, unit="iB", unit_scale=True, unit_divisor=1024) as bar:
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            bar.update(len(chunk))

            tmp_path.rename(model_path)
            print(f"Saved to {model_path}\n")

        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise RuntimeError(f"Download failed: {e}")

    return model_path
