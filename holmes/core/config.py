import os

config_path_dir: str = os.environ.get(
    "CONFIG_PATH_DIR", os.path.expanduser("~/.holmes")
)
