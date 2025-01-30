import json
import os
import logging


def write_json_file(json_output_file: str, json_ob_to_dump):
    try:
        dirname = os.path.dirname(json_output_file)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(json_output_file, "w", encoding="utf-8") as f:
            json.dump(json_ob_to_dump, f, ensure_ascii=False, indent=4, default=str)
    except Exception:
        logging.exception("Failed to create the json file.")
        return
