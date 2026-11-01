from __future__ import annotations

import os
import re
from pathlib import Path


_VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def load_local_environment(path: Path) -> None:
    """Load local KEY=VALUE settings without overriding the process environment."""
    try:
        contents = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return
    except OSError as error:
        raise RuntimeError(f"Could not read local configuration file: {path}") from error

    for line_number, raw_line in enumerate(contents.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or not _VARIABLE_NAME.fullmatch(name):
            raise ValueError(
                f"Invalid setting in local configuration file at line {line_number}."
            )

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()

        if value:
            os.environ.setdefault(name, value)
