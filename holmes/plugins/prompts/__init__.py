import os
import os.path

THIS_DIR = os.path.dirname(__file__)

def load_prompt(prompt: str) -> str:
    """
    filename is either in the format 'builtin://' or 'file://' or a regular string
    builtins are loaded as a file from this directory
    files are loaded from the file system normally
    regular strings are returned as is (as literal strings)
    """
    if prompt.startswith("builtin://"):
        path = os.path.join(THIS_DIR, prompt[len("builtin://"):])
    elif prompt.startswith("file://"):
        path = prompt[len("file://"):]
    else:
        return prompt
    
    return open(path).read()
