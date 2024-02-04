import hashlib
from pathlib import Path
import json_stream
import json_stream.base
import json

from tools.config_format import Config


# Relative to the data directory
OREDICT_FILENAME = "oredict.csv"
HANDLERS_FILENAME = "handlers.csv"
STACKS_FILENAME = "recipes_stacks.json"
RECIPES_INPUT_FILENAME = "recipes.json"
RECIPES_PREPROCESSED_FILENAME = "recipes_preprocessed.json"
RECIPES_FILTERED_FILENAME = "recipes_filtered.json"


# Relative to the local directory
CONFIG_PATH = "config.json"


def get_hash(file: Path) -> str:
    with open(file, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def check_cache_up_to_date(output_file: Path, sha: str) -> bool:
    if output_file.exists():
        print(f"Cached recipe file found at {output_file}, checking if it's up to date")
        # Check if the file is up to date
        with open(output_file, "r") as f:
            file = json_stream.load(f)
            if (
                isinstance(file, json_stream.base.TransientStreamingJSONObject)
                and file["dump_sha"] == sha
            ):
                print("Cached recipe file is up to date!")
                return True
        print("Cached recipe file is not up to date!")
    return False


def parse_json(filename, class_type, encoding="utf-8"):
    with open(filename, "r", encoding=encoding) as f:
        return class_type(**json.load(f))


def load_config() -> Config:
    with open(CONFIG_PATH, "r") as f:
        return Config(**json.load(f))
