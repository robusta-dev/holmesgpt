import os
import subprocess
import sys
import logging
from pathlib import Path
import dunamai as dunamai

# For relative imports to work in Python 3.6 - see https://stackoverflow.com/a/49375740
this_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(this_path)

# This is patched by github actions during release
# TODO: now that we are using dunamai we can probably do something better with it and not patch in github actions
__version__ = "0.0.0"


def get_version() -> str:
    # the version string was patched by a release - return __version__ which will be correct
    if not __version__.startswith("0.0.0"):
        return __version__

    version = dunamai.get_version(
        "holmes-gpt",
        first_choice=lambda: dunamai.Version.from_git(
            pattern=dunamai.Pattern.DefaultUnprefixed, path=this_path
        ),
    )
    return version.serialize(format="{base}-{branch}-{commit}-{dirty}")
