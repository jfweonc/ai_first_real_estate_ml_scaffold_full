from __future__ import annotations

import pathlib


def ensure_dir(p: str | pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path
