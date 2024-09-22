import os
import os.path
from jinja2 import Environment, FileSystemLoader

THIS_DIR = os.path.abspath(os.path.dirname(__file__))

def load_prompt(prompt: str) -> str:
    """
    prompt is either in the format 'builtin://' or 'file://' or a regular string
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

def load_and_render_prompt(prompt: str, context: dict = None) -> str:
    """
    prompt is in the format 'builtin://' or 'file://' or a regular string
    see load_prompt() for details

    context is a dictionary of variables to be passed to the jinja2 template
    """
    prompt_as_str = load_prompt(prompt)

    env = Environment(
        loader=FileSystemLoader(THIS_DIR),
    )
    template = env.from_string(prompt_as_str)

    if context is None:
        context = {}

    return template.render(**context)
