from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def glossary_path() -> Path:
    return resource_root() / "config" / "mortgage_glossary.json"


def macos_helper_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "AudioTap"
    return Path(__file__).resolve().parent.parent / "native" / "macos" / "AudioTap"
